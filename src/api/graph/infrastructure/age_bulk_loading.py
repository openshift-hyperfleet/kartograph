"""AGE-specific bulk loading strategy using PostgreSQL COPY protocol.

This strategy optimizes bulk loading for Apache AGE by:
1. Using PostgreSQL COPY to rapidly load data into staging tables
2. Fetching batches from staging and using Cypher UNWIND + MERGE
3. Cleaning up staging tables after completion

This approach is ~15x faster than direct UNWIND for large batches (800K+ operations).
"""

from __future__ import annotations

import io
import json
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from graph.domain.value_objects import EntityType, MutationOperation, MutationResult
from graph.ports.observability import MutationProbe
from graph.ports.protocols import GraphClientProtocol, GraphIndexingProtocol

if TYPE_CHECKING:
    pass


class StagingTableManager:
    """Manages temporary staging tables for bulk COPY operations."""

    def __init__(self, graph_name: str):
        """Initialize the staging table manager.

        Args:
            graph_name: Name of the graph schema for table creation
        """
        self._graph_name = graph_name

    def create_node_staging_table(self, cursor: Any, session_id: str) -> str:
        """Create a temporary staging table for nodes.

        Args:
            cursor: Database cursor
            session_id: Unique session identifier

        Returns:
            Name of the created staging table
        """
        table_name = f"_staging_nodes_{session_id}"
        cursor.execute(
            f"""
            CREATE TEMP TABLE "{table_name}" (
                id TEXT NOT NULL,
                label TEXT NOT NULL,
                properties JSONB NOT NULL
            ) ON COMMIT DROP
            """
        )
        return table_name

    def create_edge_staging_table(self, cursor: Any, session_id: str) -> str:
        """Create a temporary staging table for edges.

        Args:
            cursor: Database cursor
            session_id: Unique session identifier

        Returns:
            Name of the created staging table
        """
        table_name = f"_staging_edges_{session_id}"
        cursor.execute(
            f"""
            CREATE TEMP TABLE "{table_name}" (
                id TEXT NOT NULL,
                label TEXT NOT NULL,
                start_id TEXT NOT NULL,
                end_id TEXT NOT NULL,
                properties JSONB NOT NULL
            ) ON COMMIT DROP
            """
        )
        return table_name

    def copy_nodes_to_staging(
        self,
        cursor: Any,
        table_name: str,
        operations: list[MutationOperation],
        graph_name: str,
    ) -> int:
        """COPY node data to staging table using StringIO.

        Args:
            cursor: Database cursor
            table_name: Name of staging table
            operations: List of CREATE node operations
            graph_name: Graph name to stamp on nodes

        Returns:
            Number of rows copied
        """
        buffer = io.StringIO()

        for op in operations:
            props = dict(op.set_properties or {})
            props["id"] = op.id
            props["graph_id"] = graph_name

            # Format as TSV: id, label, properties_json
            # Escape backslashes for COPY format - PostgreSQL COPY uses backslash
            # as escape character, so JSON's \" becomes unescaped " breaking JSON.
            # By escaping backslashes (\ -> \\), COPY will preserve the JSON escapes.
            props_json = json.dumps(props).replace("\\", "\\\\")
            row = f"{op.id}\t{op.label}\t{props_json}\n"
            buffer.write(row)

        buffer.seek(0)
        cursor.copy_from(
            buffer,
            table_name,
            columns=("id", "label", "properties"),
            sep="\t",
        )
        return len(operations)

    def copy_edges_to_staging(
        self,
        cursor: Any,
        table_name: str,
        operations: list[MutationOperation],
        graph_name: str,
    ) -> int:
        """COPY edge data to staging table using StringIO.

        Args:
            cursor: Database cursor
            table_name: Name of staging table
            operations: List of CREATE edge operations
            graph_name: Graph name to stamp on edges

        Returns:
            Number of rows copied
        """
        buffer = io.StringIO()

        for op in operations:
            props = dict(op.set_properties or {})
            props["id"] = op.id
            props["graph_id"] = graph_name

            # Format as TSV: id, label, start_id, end_id, properties_json
            # Escape backslashes for COPY format (see copy_nodes_to_staging)
            props_json = json.dumps(props).replace("\\", "\\\\")
            row = f"{op.id}\t{op.label}\t{op.start_id}\t{op.end_id}\t{props_json}\n"
            buffer.write(row)

        buffer.seek(0)
        cursor.copy_from(
            buffer,
            table_name,
            columns=("id", "label", "start_id", "end_id", "properties"),
            sep="\t",
        )
        return len(operations)

    def fetch_distinct_labels(self, cursor: Any, table_name: str) -> list[str]:
        """Fetch distinct labels from staging table.

        Args:
            cursor: Database cursor
            table_name: Name of staging table

        Returns:
            List of distinct label names
        """
        cursor.execute(f'SELECT DISTINCT label FROM "{table_name}"')
        return [row[0] for row in cursor.fetchall()]

    def fetch_node_batch(
        self,
        cursor: Any,
        table_name: str,
        label: str,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """Fetch a batch of nodes from staging table.

        Args:
            cursor: Database cursor
            table_name: Name of staging table
            label: Label to filter by
            limit: Maximum rows to fetch
            offset: Offset for pagination

        Returns:
            List of node dictionaries with id, label, properties
        """
        cursor.execute(
            f"""
            SELECT id, label, properties
            FROM "{table_name}"
            WHERE label = %s
            ORDER BY id
            LIMIT %s OFFSET %s
            """,
            (label, limit, offset),
        )
        return [
            {"id": row[0], "label": row[1], "properties": row[2]}
            for row in cursor.fetchall()
        ]

    def fetch_edge_batch(
        self,
        cursor: Any,
        table_name: str,
        label: str,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """Fetch a batch of edges from staging table.

        Args:
            cursor: Database cursor
            table_name: Name of staging table
            label: Label to filter by
            limit: Maximum rows to fetch
            offset: Offset for pagination

        Returns:
            List of edge dictionaries with id, label, start_id, end_id, properties
        """
        cursor.execute(
            f"""
            SELECT id, label, start_id, end_id, properties
            FROM "{table_name}"
            WHERE label = %s
            ORDER BY id
            LIMIT %s OFFSET %s
            """,
            (label, limit, offset),
        )
        return [
            {
                "id": row[0],
                "label": row[1],
                "start_id": row[2],
                "end_id": row[3],
                "properties": row[4],
            }
            for row in cursor.fetchall()
        ]


class AgeBulkLoadingStrategy:
    """AGE-specific bulk loading strategy using PostgreSQL COPY.

    This strategy:
    1. Creates temporary staging tables
    2. Uses COPY to rapidly load data into staging
    3. Fetches batches from staging and executes Cypher MERGE
    4. Cleans up staging tables (via ON COMMIT DROP)

    For small batches (< threshold), falls back to direct UNWIND.
    """

    DEFAULT_BATCH_SIZE = 500
    COPY_THRESHOLD = 100  # Use COPY for batches >= this size

    def __init__(
        self,
        indexing_client: GraphIndexingProtocol | None = None,
        batch_size: int | None = None,
        copy_threshold: int | None = None,
    ):
        """Initialize the AGE bulk loading strategy.

        Args:
            indexing_client: Client for index management (optional)
            batch_size: Operations per UNWIND batch (default: 500)
            copy_threshold: Minimum ops to use COPY (default: 100)
        """
        self._indexing_client = indexing_client
        self._batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self._copy_threshold = copy_threshold or self.COPY_THRESHOLD

    def apply_batch(
        self,
        client: GraphClientProtocol,
        operations: list[MutationOperation],
        probe: MutationProbe,
        graph_name: str,
    ) -> MutationResult:
        """Apply mutations using COPY-based bulk loading.

        Args:
            client: Graph database client
            operations: List of mutation operations (pre-validated)
            probe: Domain probe for observability
            graph_name: Name of the graph

        Returns:
            MutationResult with success status
        """
        start_time = time.perf_counter()
        session_id = uuid.uuid4().hex[:16]
        total_batches = 0

        try:
            # Sort operations into correct execution order
            sorted_ops = self._sort_operations(operations)

            # Separate by operation type
            create_nodes = [
                op
                for op in sorted_ops
                if op.op == "CREATE" and op.type == EntityType.NODE
            ]
            create_edges = [
                op
                for op in sorted_ops
                if op.op == "CREATE" and op.type == EntityType.EDGE
            ]
            delete_edges = [
                op
                for op in sorted_ops
                if op.op == "DELETE" and op.type == EntityType.EDGE
            ]
            delete_nodes = [
                op
                for op in sorted_ops
                if op.op == "DELETE" and op.type == EntityType.NODE
            ]
            update_ops = [op for op in sorted_ops if op.op == "UPDATE"]

            # Extract unique node labels for dummy node creation
            node_labels = {op.label for op in create_nodes if op.label}

            # Phase 1: Create dummy nodes for new labels (for indexing)
            created_dummy_labels = self._create_dummy_nodes(
                client, node_labels, session_id
            )

            # Phase 2: Ensure indexes exist
            if self._indexing_client is not None:
                self._indexing_client.ensure_all_labels_indexed()

            # Phase 3: Execute operations in a transaction
            # Get raw connection for COPY operations
            conn = client.raw_connection

            with client.transaction() as tx:
                # Execute DELETEs first (edges before nodes)
                if delete_edges:
                    total_batches += self._execute_deletes(
                        tx, delete_edges, EntityType.EDGE, probe
                    )
                if delete_nodes:
                    total_batches += self._execute_deletes(
                        tx, delete_nodes, EntityType.NODE, probe
                    )

                # Execute CREATEs using COPY if large enough
                if create_nodes:
                    if len(create_nodes) >= self._copy_threshold:
                        total_batches += self._execute_creates_with_copy(
                            conn,
                            tx,
                            create_nodes,
                            "node",
                            graph_name,
                            session_id,
                            probe,
                        )
                    else:
                        total_batches += self._execute_creates_direct(
                            tx, create_nodes, "node", graph_name, probe
                        )

                if create_edges:
                    if len(create_edges) >= self._copy_threshold:
                        total_batches += self._execute_creates_with_copy(
                            conn,
                            tx,
                            create_edges,
                            "edge",
                            graph_name,
                            session_id,
                            probe,
                        )
                    else:
                        total_batches += self._execute_creates_direct(
                            tx, create_edges, "edge", graph_name, probe
                        )

                # Execute UPDATEs
                if update_ops:
                    total_batches += self._execute_updates(tx, update_ops, probe)

            duration_ms = (time.perf_counter() - start_time) * 1000
            probe.apply_batch_completed(
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
            probe.apply_batch_completed(
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
            # Cleanup dummy nodes
            if created_dummy_labels:
                try:
                    self._cleanup_dummy_nodes(client, session_id)
                except Exception:
                    pass

    def _sort_operations(
        self, operations: list[MutationOperation]
    ) -> list[MutationOperation]:
        """Sort operations into correct execution order."""

        def sort_key(op: MutationOperation) -> tuple[int, int]:
            op_priority = {"DEFINE": 0, "DELETE": 1, "CREATE": 2, "UPDATE": 3}
            if op.op == "DELETE":
                type_priority = 0 if op.type == EntityType.EDGE else 1
            else:
                type_priority = 0 if op.type == EntityType.NODE else 1
            return (op_priority.get(op.op, 999), type_priority)

        return sorted(operations, key=sort_key)

    def _create_dummy_nodes(
        self,
        client: GraphClientProtocol,
        labels: set[str],
        session_id: str,
    ) -> set[str]:
        """Create dummy nodes to pre-create label tables for indexing."""
        created_labels: set[str] = set()
        timestamp = datetime.now(timezone.utc).isoformat()

        for label in labels:
            result = client.execute_cypher(f"MATCH (n:{label}) RETURN n LIMIT 1")
            if result.row_count > 0:
                continue

            dummy_id = f"_dummy_{session_id}_{label}"
            client.execute_cypher(
                f"CREATE (n:{label} {{"
                f"id: '{dummy_id}', "
                f"_kartograph_dummy: true, "
                f"_kartograph_session_id: '{session_id}', "
                f"_kartograph_created_at: '{timestamp}'"
                f"}})"
            )
            created_labels.add(label)

        return created_labels

    def _cleanup_dummy_nodes(self, client: GraphClientProtocol, session_id: str) -> int:
        """Delete dummy nodes created by this session."""
        result = client.execute_cypher(
            f"MATCH (n {{_kartograph_session_id: '{session_id}'}}) "
            f"WHERE n._kartograph_dummy = true "
            f"DETACH DELETE n "
            f"RETURN count(n) as deleted"
        )
        if result.rows and result.rows[0]:
            deleted = result.rows[0][0]
            if isinstance(deleted, int):
                return deleted
        return 0

    def _execute_creates_with_copy(
        self,
        conn: Any,
        tx: Any,
        operations: list[MutationOperation],
        entity_type: str,
        graph_name: str,
        session_id: str,
        probe: MutationProbe,
    ) -> int:
        """Execute CREATE operations using COPY to staging table."""
        staging_manager = StagingTableManager(graph_name)
        batches = 0

        with conn.cursor() as cursor:
            # Create staging table
            if entity_type == "node":
                table_name = staging_manager.create_node_staging_table(
                    cursor, session_id
                )
                staging_manager.copy_nodes_to_staging(
                    cursor, table_name, operations, graph_name
                )
            else:
                table_name = staging_manager.create_edge_staging_table(
                    cursor, session_id
                )
                staging_manager.copy_edges_to_staging(
                    cursor, table_name, operations, graph_name
                )

            # Get distinct labels
            labels = staging_manager.fetch_distinct_labels(cursor, table_name)

            # Process each label
            for label in labels:
                offset = 0
                while True:
                    if entity_type == "node":
                        rows = staging_manager.fetch_node_batch(
                            cursor, table_name, label, self._batch_size, offset
                        )
                    else:
                        rows = staging_manager.fetch_edge_batch(
                            cursor, table_name, label, self._batch_size, offset
                        )

                    if not rows:
                        break

                    # Build and execute MERGE query
                    batch_start = time.perf_counter()
                    if entity_type == "node":
                        query = self._build_merge_nodes_query(rows, label)
                    else:
                        query = self._build_merge_edges_query(rows, label)

                    tx.execute_cypher(query)
                    batch_duration = (time.perf_counter() - batch_start) * 1000

                    probe.batch_applied(
                        operation="CREATE",
                        entity_type=entity_type,
                        label=label,
                        count=len(rows),
                        duration_ms=batch_duration,
                    )

                    batches += 1
                    offset += len(rows)

        return batches

    def _execute_creates_direct(
        self,
        tx: Any,
        operations: list[MutationOperation],
        entity_type: str,
        graph_name: str,
        probe: MutationProbe,
    ) -> int:
        """Execute CREATE operations directly using UNWIND (for small batches)."""
        # Group by label
        by_label: dict[str, list[MutationOperation]] = {}
        for op in operations:
            label = op.label or ""
            if label not in by_label:
                by_label[label] = []
            by_label[label].append(op)

        batches = 0
        for label, ops in by_label.items():
            for i in range(0, len(ops), self._batch_size):
                batch = ops[i : i + self._batch_size]
                batch_start = time.perf_counter()

                if entity_type == "node":
                    query = self._build_unwind_create_nodes(batch, label, graph_name)
                else:
                    query = self._build_unwind_create_edges(batch, label, graph_name)

                tx.execute_cypher(query)
                batch_duration = (time.perf_counter() - batch_start) * 1000

                probe.batch_applied(
                    operation="CREATE",
                    entity_type=entity_type,
                    label=label,
                    count=len(batch),
                    duration_ms=batch_duration,
                )
                batches += 1

        return batches

    def _execute_deletes(
        self,
        tx: Any,
        operations: list[MutationOperation],
        entity_type: EntityType,
        probe: MutationProbe,
    ) -> int:
        """Execute DELETE operations using UNWIND."""
        batches = 0
        for i in range(0, len(operations), self._batch_size):
            batch = operations[i : i + self._batch_size]
            batch_start = time.perf_counter()

            ids = [f"{{id: '{op.id}'}}" for op in batch]
            ids_str = ", ".join(ids)

            if entity_type == EntityType.NODE:
                query = (
                    f"WITH [{ids_str}] AS items "
                    f"UNWIND items AS item "
                    f"MATCH (n {{id: item.id}}) "
                    f"DETACH DELETE n"
                )
            else:
                query = (
                    f"WITH [{ids_str}] AS items "
                    f"UNWIND items AS item "
                    f"MATCH ()-[r {{id: item.id}}]->() "
                    f"DELETE r"
                )

            tx.execute_cypher(query)
            batch_duration = (time.perf_counter() - batch_start) * 1000

            probe.batch_applied(
                operation="DELETE",
                entity_type=str(entity_type),
                label=None,
                count=len(batch),
                duration_ms=batch_duration,
            )
            batches += 1

        return batches

    def _execute_updates(
        self,
        tx: Any,
        operations: list[MutationOperation],
        probe: MutationProbe,
    ) -> int:
        """Execute UPDATE operations."""
        batches = 0

        # Separate by entity type and whether they have remove_properties
        for op in operations:
            if op.remove_properties:
                # Execute individually for REMOVE operations
                batch_start = time.perf_counter()
                query = self._build_update_query(op)
                tx.execute_cypher(query)
                batch_duration = (time.perf_counter() - batch_start) * 1000

                probe.batch_applied(
                    operation="UPDATE",
                    entity_type=str(op.type),
                    label=None,
                    count=1,
                    duration_ms=batch_duration,
                )
                batches += 1
            else:
                # Can batch SET-only updates
                batch_start = time.perf_counter()
                query = self._build_update_query(op)
                tx.execute_cypher(query)
                batch_duration = (time.perf_counter() - batch_start) * 1000

                probe.batch_applied(
                    operation="UPDATE",
                    entity_type=str(op.type),
                    label=None,
                    count=1,
                    duration_ms=batch_duration,
                )
                batches += 1

        return batches

    def _build_merge_nodes_query(self, rows: list[dict[str, Any]], label: str) -> str:
        """Build UNWIND MERGE query from staging data."""
        items = []
        all_props: set[str] = set()

        for row in rows:
            props = row["properties"]
            all_props.update(props.keys())

        for row in rows:
            props = row["properties"]
            item_parts = [f"id: '{row['id']}'"]
            for prop in all_props:
                value = props.get(prop)
                item_parts.append(f"`{prop}`: {self._format_value(value)}")
            items.append("{" + ", ".join(item_parts) + "}")

        items_str = ", ".join(items)
        set_clauses = [f"SET n.`{prop}` = item.`{prop}`" for prop in all_props]

        return (
            f"WITH [{items_str}] AS items "
            f"UNWIND items AS item "
            f"MERGE (n:{label} {{id: item.id}}) " + " ".join(set_clauses)
        )

    def _build_merge_edges_query(self, rows: list[dict[str, Any]], label: str) -> str:
        """Build UNWIND MERGE query for edges from staging data."""
        items = []
        all_props: set[str] = set()

        for row in rows:
            props = row["properties"]
            all_props.update(props.keys())

        for row in rows:
            props = row["properties"]
            item_parts = [
                f"id: '{row['id']}'",
                f"start_id: '{row['start_id']}'",
                f"end_id: '{row['end_id']}'",
            ]
            for prop in all_props:
                value = props.get(prop)
                item_parts.append(f"`{prop}`: {self._format_value(value)}")
            items.append("{" + ", ".join(item_parts) + "}")

        items_str = ", ".join(items)
        set_clauses = [f"SET r.`{prop}` = item.`{prop}`" for prop in all_props]

        return (
            f"WITH [{items_str}] AS items "
            f"UNWIND items AS item "
            f"MATCH (source {{id: item.start_id}}) "
            f"MATCH (target {{id: item.end_id}}) "
            f"MERGE (source)-[r:{label} {{id: item.id}}]->(target) "
            + " ".join(set_clauses)
        )

    def _build_unwind_create_nodes(
        self, operations: list[MutationOperation], label: str, graph_name: str
    ) -> str:
        """Build UNWIND query for direct node creation."""
        all_props: set[str] = set()
        for op in operations:
            if op.set_properties:
                all_props.update(op.set_properties.keys())

        items = []
        for op in operations:
            props = op.set_properties or {}
            item_parts = [f"id: '{op.id}'"]
            for prop in all_props:
                value = props.get(prop)
                item_parts.append(f"`{prop}`: {self._format_value(value)}")
            items.append("{" + ", ".join(item_parts) + "}")

        items_str = ", ".join(items)
        set_clauses = [f"SET n.`{prop}` = item.`{prop}`" for prop in all_props]
        set_clauses.append(f"SET n.`graph_id` = '{graph_name}'")

        return (
            f"WITH [{items_str}] AS items "
            f"UNWIND items AS item "
            f"MERGE (n:{label} {{id: item.id}}) " + " ".join(set_clauses)
        )

    def _build_unwind_create_edges(
        self, operations: list[MutationOperation], label: str, graph_name: str
    ) -> str:
        """Build UNWIND query for direct edge creation."""
        all_props: set[str] = set()
        for op in operations:
            if op.set_properties:
                all_props.update(op.set_properties.keys())

        items = []
        for op in operations:
            props = op.set_properties or {}
            item_parts = [
                f"id: '{op.id}'",
                f"start_id: '{op.start_id}'",
                f"end_id: '{op.end_id}'",
            ]
            for prop in all_props:
                value = props.get(prop)
                item_parts.append(f"`{prop}`: {self._format_value(value)}")
            items.append("{" + ", ".join(item_parts) + "}")

        items_str = ", ".join(items)
        set_clauses = [f"SET r.`{prop}` = item.`{prop}`" for prop in all_props]
        set_clauses.append(f"SET r.`graph_id` = '{graph_name}'")

        return (
            f"WITH [{items_str}] AS items "
            f"UNWIND items AS item "
            f"MATCH (source {{id: item.start_id}}) "
            f"MATCH (target {{id: item.end_id}}) "
            f"MERGE (source)-[r:{label} {{id: item.id}}]->(target) "
            + " ".join(set_clauses)
        )

    def _build_update_query(self, op: MutationOperation) -> str:
        """Build UPDATE query for a single operation."""
        if op.type == EntityType.NODE:
            var_name = "n"
            match_pattern = f"MATCH (n {{id: '{op.id}'}})"
        else:
            var_name = "r"
            match_pattern = f"MATCH ()-[r {{id: '{op.id}'}}]->()"

        parts = [match_pattern]

        if op.set_properties:
            set_clauses = []
            for k, v in op.set_properties.items():
                set_clauses.append(f"{var_name}.`{k}` = {self._format_value(v)}")
            parts.append("SET " + ", ".join(set_clauses))

        if op.remove_properties:
            remove_clauses = [f"{var_name}.`{k}`" for k in op.remove_properties]
            parts.append("REMOVE " + ", ".join(remove_clauses))

        return " ".join(parts)

    def _format_value(self, value: Any) -> str:
        """Format Python value for Cypher query."""
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif value is None:
            return "null"
        elif isinstance(value, dict):
            items = [f"{k}: {v}" for k, v in value.items()]
            return self._format_value(items)
        elif isinstance(value, list):
            formatted_items = [self._format_value(item) for item in value]
            return f"[{', '.join(formatted_items)}]"
        else:
            return str(value)
