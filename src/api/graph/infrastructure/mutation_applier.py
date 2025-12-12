"""Mutation applier for Graph bounded context.

Applies mutation operations to the graph database in transactional batches.
Uses Domain-Oriented Observability for tracking.
"""

from __future__ import annotations

from typing import Any

from graph.domain.value_objects import MutationOperation, MutationResult
from graph.infrastructure.observability import DefaultMutationProbe, MutationProbe
from graph.infrastructure.protocols import GraphClientProtocol


class MutationApplier:
    """Applies mutation operations to the graph database.

    All operations are applied within a transaction for atomicity.
    Uses Domain-Oriented Observability for tracking.
    """

    def __init__(
        self,
        client: GraphClientProtocol,
        probe: MutationProbe | None = None,
    ):
        """Initialize the mutation applier.

        Args:
            client: Graph database client for executing queries
            probe: Domain probe for observability (optional, defaults to DefaultMutationProbe)
        """
        self._client = client
        self._probe = probe or DefaultMutationProbe()

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

        Args:
            operations: List of mutation operations to apply (order does not matter)

        Returns:
            MutationResult with success status and operation count
        """
        if not operations:
            return MutationResult(
                success=True,
                operations_applied=0,
            )

        try:
            # Validate all operations before executing
            for op in operations:
                op.validate_operation()

            # Sort operations into correct execution order
            sorted_ops = self._sort_operations(operations)

            # Execute all operations in a transaction
            with self._client.transaction() as tx:
                for op in sorted_ops:
                    query = self._build_query(op)
                    if query is not None:
                        tx.execute_cypher(query)
                    self._probe.mutation_applied(
                        operation=op.op,
                        entity_type=op.type,
                        entity_id=op.id,
                    )

            return MutationResult(
                success=True,
                operations_applied=len(operations),
            )
        except Exception as e:
            return MutationResult(
                success=False,
                operations_applied=0,
                errors=[str(e)],
            )

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

    def _build_query(self, op: MutationOperation) -> str | None:
        """Build Cypher query for mutation operation.

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

        Args:
            op: The CREATE operation

        Returns:
            Cypher MERGE query
        """
        if op.type == "node":
            # MERGE on id, set all properties
            set_clauses = []
            for k, v in (op.set_properties or {}).items():
                set_clauses.append(f"SET n.{k} = {self._format_value(v)}")

            return f"MERGE (n:{op.label} {{id: '{op.id}'}}) " + " ".join(set_clauses)
        else:  # edge
            # MERGE on id, match source/target nodes, set properties
            set_clauses = []
            for k, v in (op.set_properties or {}).items():
                set_clauses.append(f"SET r.{k} = {self._format_value(v)}")

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
        parts = [f"MATCH (n {{id: '{op.id}'}})"]

        if op.set_properties:
            set_clauses = []
            for k, v in op.set_properties.items():
                set_clauses.append(f"n.{k} = {self._format_value(v)}")
            parts.append("SET " + ", ".join(set_clauses))

        if op.remove_properties:
            remove_clauses = [f"n.{k}" for k in op.remove_properties]
            parts.append("REMOVE " + ", ".join(remove_clauses))

        return " ".join(parts)

    def _build_delete(self, op: MutationOperation) -> str:
        """Build DELETE query with cascade (DETACH).

        Args:
            op: The DELETE operation

        Returns:
            Cypher DETACH DELETE query
        """
        return f"MATCH (n {{id: '{op.id}'}}) DETACH DELETE n"

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
        else:
            return str(value)
