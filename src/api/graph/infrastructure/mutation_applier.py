"""Mutation applier for Graph bounded context.

Applies mutation operations to the graph database in transactional batches.
Uses Domain-Oriented Observability for tracking.

Performance optimization: Uses UNWIND for batch operations to minimize
round-trips when applying large numbers of mutations.

Index optimization: For new labels, creates temporary dummy nodes to
pre-create label tables, then creates indexes before the main transaction.
This ensures MATCH operations use indexes even on first insert.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from graph.domain.value_objects import EntityType, MutationOperation, MutationResult
from graph.infrastructure.observability import DefaultMutationProbe, MutationProbe
from graph.ports.protocols import GraphClientProtocol


class OperationGroup(TypedDict):
    """A group of operations to be executed as a batch."""

    op: str
    entity_type: str
    label: str | None
    operations: list[MutationOperation]


class MutationApplier:
    """Applies mutation operations to the graph database.

    All operations are applied within a transaction for atomicity.
    Uses Domain-Oriented Observability for tracking.

    Performance optimization: Operations are batched using UNWIND to
    reduce database round-trips. A batch of 200 CREATE operations
    executes as a single query instead of 200 separate queries.
    """

    DEFAULT_BATCH_SIZE = 200

    def __init__(
        self,
        client: GraphClientProtocol,
        probe: MutationProbe | None = None,
        batch_size: int | None = None,
    ):
        """Initialize the mutation applier.

        Args:
            client: Graph database client for executing queries
            probe: Domain probe for observability (optional, defaults to DefaultMutationProbe)
            batch_size: Maximum operations per UNWIND batch (default: 200)
        """
        self._client = client
        self._probe = probe or DefaultMutationProbe()
        self._batch_size = batch_size or self.DEFAULT_BATCH_SIZE

    def _extract_labels(self, operations: list[MutationOperation]) -> set[str]:
        """Extract all unique labels from CREATE NODE operations.

        Only extracts node labels because edge labels cannot be pre-created
        as dummy nodes in AGE (edge labels are for edges, not vertices).

        Args:
            operations: List of mutation operations

        Returns:
            Set of unique node label names
        """
        labels: set[str] = set()
        for op in operations:
            if op.op == "CREATE" and op.type == EntityType.NODE and op.label:
                labels.add(op.label)
        return labels

    def _create_dummy_nodes(
        self,
        labels: set[str],
        session_id: str,
    ) -> set[str]:
        """Create dummy nodes to pre-create label tables for indexing.

        Creates a temporary node for each label that doesn't exist yet.
        These nodes have special metadata for identification and cleanup.

        Args:
            labels: Set of labels that need to exist
            session_id: Unique identifier for this session (for cleanup)

        Returns:
            Set of labels for which dummy nodes were created
        """
        created_labels: set[str] = set()
        timestamp = datetime.now(timezone.utc).isoformat()

        for label in labels:
            # Check if label already exists
            result = self._client.execute_cypher(f"MATCH (n:{label}) RETURN n LIMIT 1")
            if result.row_count > 0:
                continue

            # Create dummy node with cleanup metadata
            dummy_id = f"_dummy_{session_id}_{label}"
            self._client.execute_cypher(
                f"CREATE (n:{label} {{"
                f"id: '{dummy_id}', "
                f"_kartograph_dummy: true, "
                f"_kartograph_session_id: '{session_id}', "
                f"_kartograph_created_at: '{timestamp}'"
                f"}})"
            )
            created_labels.add(label)

        return created_labels

    def _cleanup_dummy_nodes(self, session_id: str) -> int:
        """Delete dummy nodes created by this session.

        Args:
            session_id: The session ID used when creating dummies

        Returns:
            Number of dummy nodes deleted
        """
        result = self._client.execute_cypher(
            f"MATCH (n {{_kartograph_session_id: '{session_id}'}}) "
            f"WHERE n._kartograph_dummy = true "
            f"DETACH DELETE n "
            f"RETURN count(n) as deleted"
        )
        if result.rows and result.rows[0]:
            # AGE returns the count differently, handle both cases
            deleted = result.rows[0][0]
            if isinstance(deleted, int):
                return deleted
        return 0

    def apply_batch(
        self,
        operations: list[MutationOperation],
    ) -> MutationResult:
        """Apply a batch of mutations atomically.

        All operations are executed within a single transaction. If any operation
        fails, the entire batch is rolled back.

        Operations are automatically sorted into the correct execution order:
        1. DEFINE
        2. DELETE <edge>
        3. DELETE <node>
        4. CREATE <node>
        5. CREATE <edge>
        6. UPDATE <node>
        7. UPDATE <edge>

        Performance: Operations of the same type are batched using UNWIND
        to minimize database round-trips.

        Args:
            operations: List of mutation operations to apply (order does not matter)

        Returns:
            MutationResult with success status and operation count
        """
        if not operations:
            self._probe.apply_batch_completed(
                total_operations=0,
                total_batches=0,
                duration_ms=0.0,
                success=True,
            )
            return MutationResult(
                success=True,
                operations_applied=0,
            )

        start_time = time.perf_counter()
        total_batches = 0
        session_id = str(uuid.uuid4())
        created_dummy_labels: set[str] = set()

        try:
            # Validate all operations before executing
            for op in operations:
                op.validate_operation()

            # Sort operations into correct execution order
            sorted_ops = self._sort_operations(operations)

            # Group operations for batching
            groups = self._group_operations(sorted_ops)

            # Extract labels from operations to ensure they exist for indexing
            labels = self._extract_labels(operations)

            # Phase 1: Create dummy nodes for new labels (outside main transaction)
            # This creates the label tables in PostgreSQL so we can create indexes
            created_dummy_labels = self._create_dummy_nodes(labels, session_id)

            # Phase 2: Ensure all labels (existing + newly created) have indexes
            # This is critical for performance - without indexes, MATCH operations
            # do full table scans which is extremely slow for large graphs
            self._client.ensure_all_labels_indexed()

            # Phase 3: Execute all batched operations in a transaction
            with self._client.transaction() as tx:
                for group in groups:
                    total_batches += self._execute_group(tx, group)

            duration_ms = (time.perf_counter() - start_time) * 1000
            self._probe.apply_batch_completed(
                total_operations=len(operations),
                total_batches=total_batches,
                duration_ms=duration_ms,
                success=True,
            )

            return MutationResult(
                success=True,
                operations_applied=len(operations),
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._probe.apply_batch_completed(
                total_operations=len(operations),
                total_batches=total_batches,
                duration_ms=duration_ms,
                success=False,
            )
            return MutationResult(
                success=False,
                operations_applied=0,
                errors=[str(e)],
            )
        finally:
            # Phase 4: Clean up dummy nodes (always, success or failure)
            # This runs outside the main transaction to ensure cleanup happens
            if created_dummy_labels:
                try:
                    self._cleanup_dummy_nodes(session_id)
                except Exception:
                    # Log but don't fail - orphaned dummies can be cleaned up later
                    # via _kartograph_dummy metadata
                    pass

    def _sort_operations(
        self,
        operations: list[MutationOperation],
    ) -> list[MutationOperation]:
        """Sort operations into correct execution order.

        Order:
        1. DEFINE
        2. DELETE <edge>
        3. DELETE <node>
        4. CREATE <node>
        5. CREATE <edge>
        6. UPDATE <node>
        7. UPDATE <edge>

        Args:
            operations: Unsorted list of operations

        Returns:
            Operations sorted in correct execution order
        """

        def sort_key(op: MutationOperation) -> tuple[int, int]:
            """Generate sort key for operation.

            Returns tuple of (operation_priority, entity_type_priority)
            """
            # Operation priority
            op_priority = {
                "DEFINE": 0,
                "DELETE": 1,
                "CREATE": 2,
                "UPDATE": 3,
            }

            # Entity type priority (edges before nodes for DELETE, nodes before edges for CREATE/UPDATE)
            if op.op == "DELETE":
                type_priority = 0 if op.type == "edge" else 1
            else:  # CREATE or UPDATE
                type_priority = 0 if op.type == "node" else 1

            return (op_priority.get(op.op, 999), type_priority)

        return sorted(operations, key=sort_key)

    def _group_operations(
        self,
        operations: list[MutationOperation],
    ) -> list[OperationGroup]:
        """Group operations for batched execution.

        CREATE operations are grouped by label (required for MERGE syntax).
        DELETE and UPDATE operations are grouped by entity type only.
        DEFINE operations are skipped (handled by TypeDefinitionRepository).

        Uses dictionary-based grouping to collect ALL operations with the same
        key, not just consecutive ones. This ensures maximum batching efficiency.

        Args:
            operations: Sorted list of operations

        Returns:
            List of operation groups ready for batch execution, ordered by
            the execution priority (DELETE edges, DELETE nodes, CREATE nodes,
            CREATE edges, UPDATE nodes, UPDATE edges)
        """
        # Use a dict to collect operations by key
        # Key format: (op_type, entity_type, label_or_none)
        # MutationOperationType and EntityType are str enums, use directly as dict keys
        group_dict: dict[tuple[str, str, str | None], list[MutationOperation]] = {}
        individual_ops: list[OperationGroup] = []

        for op in operations:
            if op.op == "DEFINE":
                # DEFINE operations don't modify the database
                continue

            # UPDATE with remove_properties can't be batched efficiently
            if op.op == "UPDATE" and op.remove_properties:
                individual_ops.append(
                    OperationGroup(
                        op=op.op,
                        entity_type=op.type,
                        label=None,
                        operations=[op],
                    )
                )
                continue

            # Determine grouping key
            # MutationOperationType and EntityType are str enums, use directly
            group_key: tuple[str, str, str | None]
            if op.op == "CREATE":
                # CREATE groups by (op, entity_type, label)
                group_key = (op.op, op.type, op.label)
            else:
                # DELETE and UPDATE group by (op, entity_type)
                group_key = (op.op, op.type, None)

            # Add to appropriate group
            if group_key not in group_dict:
                group_dict[group_key] = []
            group_dict[group_key].append(op)

        # Convert dict to list of OperationGroups
        groups: list[OperationGroup] = []
        for (op_type, entity_type, label), ops in group_dict.items():
            groups.append(
                OperationGroup(
                    op=op_type,
                    entity_type=entity_type,
                    label=label,
                    operations=ops,
                )
            )

        # Sort groups by execution order (already sorted by _sort_operations,
        # but we need to maintain the order after dict grouping)
        def group_sort_key(g: OperationGroup) -> tuple[int, int]:
            op_priority = {"DELETE": 0, "CREATE": 1, "UPDATE": 2}
            if g["op"] == "DELETE":
                type_priority = 0 if g["entity_type"] == EntityType.EDGE else 1
            else:
                type_priority = 0 if g["entity_type"] == EntityType.NODE else 1
            return (op_priority.get(g["op"], 999), type_priority)

        groups.sort(key=group_sort_key)

        # Add individual operations at the end (they're UPDATE with REMOVE)
        groups.extend(individual_ops)

        return groups

    def _execute_group(self, tx: Any, group: OperationGroup) -> int:
        """Execute a group of operations in batches.

        Args:
            tx: Transaction context
            group: Group of operations to execute

        Returns:
            Number of batches executed
        """
        ops = group["operations"]
        op_type = group["op"]
        entity_type = group["entity_type"]
        label = group["label"]
        batch_count = 0

        # Split into batches
        for i in range(0, len(ops), self._batch_size):
            batch = ops[i : i + self._batch_size]

            # Build and execute the appropriate batch query
            if op_type == "CREATE":
                if entity_type == EntityType.NODE or entity_type == "node":
                    query = self._build_batch_create_nodes(batch)
                else:
                    query = self._build_batch_create_edges(batch)
            elif op_type == "DELETE":
                if entity_type == EntityType.NODE or entity_type == "node":
                    query = self._build_batch_delete_nodes(batch)
                else:
                    query = self._build_batch_delete_edges(batch)
            elif op_type == "UPDATE":
                if len(batch) == 1 and batch[0].remove_properties:
                    # Individual UPDATE with REMOVE
                    query = self._build_update(batch[0])
                elif entity_type == EntityType.NODE or entity_type == "node":
                    query = self._build_batch_update_nodes(batch)
                else:
                    query = self._build_batch_update_edges(batch)
            else:
                raise ValueError(f"Unknown operation type: {op_type}")

            batch_start = time.perf_counter()
            tx.execute_cypher(query)
            batch_duration_ms = (time.perf_counter() - batch_start) * 1000

            # Emit batch probe event with timing
            self._probe.batch_applied(
                operation=op_type,
                entity_type=entity_type,
                label=label,
                count=len(batch),
                duration_ms=batch_duration_ms,
            )
            batch_count += 1

        return batch_count

    def _build_batch_create_nodes(self, operations: list[MutationOperation]) -> str:
        """Build UNWIND query for batch node creation.

        AGE doesn't support SET n += item.props, so we flatten properties
        into the item and generate individual SET clauses.

        Args:
            operations: List of CREATE node operations (must all have same label)

        Returns:
            Cypher UNWIND query for creating all nodes
        """
        label = operations[0].label

        # Collect all unique property names across all operations
        all_prop_names: set[str] = set()
        for op in operations:
            if op.set_properties:
                all_prop_names.update(op.set_properties.keys())

        # Build array of node data with flattened properties
        items = []
        for op in operations:
            props = op.set_properties or {}
            item_parts = [f"id: '{op.id}'"]
            for prop_name in all_prop_names:
                value = props.get(prop_name)
                item_parts.append(f"`{prop_name}`: {self._format_value(value)}")
            items.append("{" + ", ".join(item_parts) + "}")

        items_str = ", ".join(items)

        # Generate individual SET clauses for each property
        set_clauses = [f"SET n.`{prop}` = item.`{prop}`" for prop in all_prop_names]
        set_clauses.append(f"SET n.`graph_id` = '{self._client.graph_name}'")

        return (
            f"WITH [{items_str}] AS items "
            f"UNWIND items AS item "
            f"MERGE (n:{label} {{id: item.id}}) " + " ".join(set_clauses)
        )

    def _build_batch_create_edges(self, operations: list[MutationOperation]) -> str:
        """Build UNWIND query for batch edge creation.

        AGE doesn't support SET r += item.props, so we flatten properties
        into the item and generate individual SET clauses.

        Args:
            operations: List of CREATE edge operations (must all have same label)

        Returns:
            Cypher UNWIND query for creating all edges
        """
        label = operations[0].label

        # Collect all unique property names across all operations
        all_prop_names: set[str] = set()
        for op in operations:
            if op.set_properties:
                all_prop_names.update(op.set_properties.keys())

        # Build array of edge data with flattened properties
        items = []
        for op in operations:
            props = op.set_properties or {}
            item_parts = [
                f"id: '{op.id}'",
                f"start_id: '{op.start_id}'",
                f"end_id: '{op.end_id}'",
            ]
            for prop_name in all_prop_names:
                value = props.get(prop_name)
                item_parts.append(f"`{prop_name}`: {self._format_value(value)}")
            items.append("{" + ", ".join(item_parts) + "}")

        items_str = ", ".join(items)

        # Generate individual SET clauses for each property
        set_clauses = [f"SET r.`{prop}` = item.`{prop}`" for prop in all_prop_names]
        set_clauses.append(f"SET r.`graph_id` = '{self._client.graph_name}'")

        return (
            f"WITH [{items_str}] AS items "
            f"UNWIND items AS item "
            f"MATCH (source {{id: item.start_id}}) "
            f"MATCH (target {{id: item.end_id}}) "
            f"MERGE (source)-[r:{label} {{id: item.id}}]->(target) "
            + " ".join(set_clauses)
        )

    def _build_batch_delete_nodes(self, operations: list[MutationOperation]) -> str:
        """Build UNWIND query for batch node deletion.

        Args:
            operations: List of DELETE node operations

        Returns:
            Cypher UNWIND query for deleting all nodes
        """
        ids = [f"{{id: '{op.id}'}}" for op in operations]
        ids_str = ", ".join(ids)

        return (
            f"WITH [{ids_str}] AS items "
            f"UNWIND items AS item "
            f"MATCH (n {{id: item.id}}) "
            f"DETACH DELETE n"
        )

    def _build_batch_delete_edges(self, operations: list[MutationOperation]) -> str:
        """Build UNWIND query for batch edge deletion.

        Args:
            operations: List of DELETE edge operations

        Returns:
            Cypher UNWIND query for deleting all edges
        """
        ids = [f"{{id: '{op.id}'}}" for op in operations]
        ids_str = ", ".join(ids)

        return (
            f"WITH [{ids_str}] AS items "
            f"UNWIND items AS item "
            f"MATCH ()-[r {{id: item.id}}]->() "
            f"DELETE r"
        )

    def _build_batch_update_nodes(self, operations: list[MutationOperation]) -> str:
        """Build UNWIND query for batch node updates.

        AGE doesn't support SET n += item.props, so we flatten properties
        into the item and generate individual SET clauses.

        Note: This only handles SET operations. Operations with remove_properties
        are handled individually.

        Args:
            operations: List of UPDATE node operations (SET only)

        Returns:
            Cypher UNWIND query for updating all nodes
        """
        # Collect all unique property names across all operations
        all_prop_names: set[str] = set()
        for op in operations:
            if op.set_properties:
                all_prop_names.update(op.set_properties.keys())

        # Build array of node data with flattened properties
        items = []
        for op in operations:
            props = op.set_properties or {}
            item_parts = [f"id: '{op.id}'"]
            for prop_name in all_prop_names:
                value = props.get(prop_name)
                item_parts.append(f"`{prop_name}`: {self._format_value(value)}")
            items.append("{" + ", ".join(item_parts) + "}")

        items_str = ", ".join(items)

        # Generate individual SET clauses for each property
        set_clauses = [f"SET n.`{prop}` = item.`{prop}`" for prop in all_prop_names]

        return (
            f"WITH [{items_str}] AS items "
            f"UNWIND items AS item "
            f"MATCH (n {{id: item.id}}) " + " ".join(set_clauses)
        )

    def _build_batch_update_edges(self, operations: list[MutationOperation]) -> str:
        """Build UNWIND query for batch edge updates.

        AGE doesn't support SET r += item.props, so we flatten properties
        into the item and generate individual SET clauses.

        Note: This only handles SET operations. Operations with remove_properties
        are handled individually.

        Args:
            operations: List of UPDATE edge operations (SET only)

        Returns:
            Cypher UNWIND query for updating all edges
        """
        # Collect all unique property names across all operations
        all_prop_names: set[str] = set()
        for op in operations:
            if op.set_properties:
                all_prop_names.update(op.set_properties.keys())

        # Build array of edge data with flattened properties
        items = []
        for op in operations:
            props = op.set_properties or {}
            item_parts = [f"id: '{op.id}'"]
            for prop_name in all_prop_names:
                value = props.get(prop_name)
                item_parts.append(f"`{prop_name}`: {self._format_value(value)}")
            items.append("{" + ", ".join(item_parts) + "}")

        items_str = ", ".join(items)

        # Generate individual SET clauses for each property
        set_clauses = [f"SET r.`{prop}` = item.`{prop}`" for prop in all_prop_names]

        return (
            f"WITH [{items_str}] AS items "
            f"UNWIND items AS item "
            f"MATCH ()-[r {{id: item.id}}]->() " + " ".join(set_clauses)
        )

    # Legacy methods for backwards compatibility with existing tests

    def _build_query(self, op: MutationOperation) -> str | None:
        """Build Cypher query for mutation operation.

        This method is maintained for backwards compatibility.
        New code should use the batch methods.

        Args:
            op: The mutation operation to convert to Cypher

        Returns:
            Cypher query string

        Raises:
            ValueError: If operation type is unknown
        """
        if op.op == "CREATE":
            return self._build_create(op)
        elif op.op == "UPDATE":
            return self._build_update(op)
        elif op.op == "DELETE":
            return self._build_delete(op)
        elif op.op == "DEFINE":
            # DEFINE operations don't modify the database, they just define schemas
            # For now, we skip them (they'll be handled by the TypeDefinitionRepository)
            return None
        else:
            raise ValueError(f"Unknown operation: {op.op}")

    def _build_create(self, op: MutationOperation) -> str:
        """Build CREATE query using MERGE for idempotency.

        Automatically stamps graph_id property on all created entities.

        Args:
            op: The CREATE operation

        Returns:
            Cypher MERGE query
        """
        if op.type == EntityType.NODE:
            # MERGE on id, set all properties
            # Use backticks around property names to avoid reserved keyword conflicts
            set_clauses = []
            for k, v in (op.set_properties or {}).items():
                set_clauses.append(f"SET n.`{k}` = {self._format_value(v)}")

            # Infrastructure automatically stamps graph_id
            set_clauses.append(f"SET n.`graph_id` = '{self._client.graph_name}'")

            return f"MERGE (n:{op.label} {{id: '{op.id}'}}) " + " ".join(set_clauses)
        else:  # edge
            # MERGE on id, match source/target nodes, set properties
            # Use backticks around property names to avoid reserved keyword conflicts
            set_clauses = []
            for k, v in (op.set_properties or {}).items():
                set_clauses.append(f"SET r.`{k}` = {self._format_value(v)}")

            # Infrastructure automatically stamps graph_id
            set_clauses.append(f"SET r.`graph_id` = '{self._client.graph_name}'")

            return (
                f"MATCH (source {{id: '{op.start_id}'}}) "
                f"MATCH (target {{id: '{op.end_id}'}}) "
                f"MERGE (source)-[r:{op.label} {{id: '{op.id}'}}]->(target) "
                + " ".join(set_clauses)
            )

    def _build_update(self, op: MutationOperation) -> str:
        """Build UPDATE query with separate SET and REMOVE.

        Args:
            op: The UPDATE operation

        Returns:
            Cypher UPDATE query
        """
        # Use appropriate syntax based on entity type
        if op.type == EntityType.NODE:
            var_name = "n"
            match_pattern = f"MATCH (n {{id: '{op.id}'}})"
        else:  # EntityType.EDGE
            var_name = "r"
            match_pattern = f"MATCH ()-[r {{id: '{op.id}'}}]->()"

        parts = [match_pattern]

        # Use backticks around property names to avoid reserved keyword conflicts
        if op.set_properties:
            set_clauses = []
            for k, v in op.set_properties.items():
                set_clauses.append(f"{var_name}.`{k}` = {self._format_value(v)}")
            parts.append("SET " + ", ".join(set_clauses))

        if op.remove_properties:
            remove_clauses = [f"{var_name}.`{k}`" for k in op.remove_properties]
            parts.append("REMOVE " + ", ".join(remove_clauses))

        return " ".join(parts)

    def _build_delete(self, op: MutationOperation) -> str:
        """Build DELETE query with cascade (DETACH).

        Args:
            op: The DELETE operation

        Returns:
            Cypher DELETE query (DETACH DELETE for nodes, DELETE for edges)
        """
        if op.type == EntityType.NODE:
            # Use DETACH DELETE for nodes to cascade edge deletions
            return f"MATCH (n {{id: '{op.id}'}}) DETACH DELETE n"
        else:  # EntityType.EDGE
            # Edges don't need DETACH, just DELETE
            return f"MATCH ()-[r {{id: '{op.id}'}}]->() DELETE r"

    def _format_map(self, props: dict[str, Any]) -> str:
        """Format a dictionary as a Cypher map.

        Uses backticks around property names to avoid reserved keyword conflicts.

        Args:
            props: Dictionary of properties

        Returns:
            Formatted Cypher map string
        """
        if not props:
            return "{}"

        items = []
        for k, v in props.items():
            # Use backticks for property names in maps
            items.append(f"`{k}`: {self._format_value(v)}")

        return "{" + ", ".join(items) + "}"

    def _format_value(self, value: Any) -> str:
        """Format Python value for Cypher query.

        Args:
            value: Python value to format

        Returns:
            Formatted string for Cypher query
        """
        if isinstance(value, str):
            # Escape backslashes
            escaped = value.replace("\\", "\\\\")
            # Escape single quotes in strings
            escaped = escaped.replace("'", "\\'")
            return f"'{escaped}'"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif value is None:
            return "null"
        elif isinstance(value, dict):
            # Convert dict to array of "key: value" strings
            # AGE has issues with map keys containing special characters like '-' or '.'
            items = [f"{k}: {v}" for k, v in value.items()]
            return self._format_value(items)
        elif isinstance(value, list):
            # Recursively format list items
            formatted_items = [self._format_value(item) for item in value]
            return f"[{', '.join(formatted_items)}]"
        else:
            return str(value)
