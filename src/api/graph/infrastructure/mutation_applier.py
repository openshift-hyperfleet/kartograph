"""Mutation applier for Graph bounded context.

Applies mutation operations to the graph database using a pluggable
bulk loading strategy. Uses Domain-Oriented Observability for tracking.

The MutationApplier is a thin coordinator that:
1. Validates operations
2. Delegates execution to a database-specific BulkLoadingStrategy

Different strategies optimize for their target database:
- AgeBulkLoadingStrategy: PostgreSQL COPY + staging tables for AGE
- Neo4jBulkLoadingStrategy (future): Large UNWIND batches
"""

from __future__ import annotations

from graph.domain.value_objects import EntityType, MutationOperation, MutationResult
from graph.infrastructure.observability import DefaultMutationProbe
from graph.ports.bulk_loading import BulkLoadingStrategy
from graph.ports.observability import MutationProbe
from graph.ports.protocols import GraphClientProtocol


class MutationApplier:
    """Applies mutation operations to the graph database.

    This is a thin coordinator that validates operations and delegates
    execution to a database-specific BulkLoadingStrategy.

    Uses Domain-Oriented Observability for tracking.
    """

    def __init__(
        self,
        client: GraphClientProtocol,
        bulk_loading_strategy: BulkLoadingStrategy,
        probe: MutationProbe | None = None,
    ):
        """Initialize the mutation applier.

        Args:
            client: Graph database client for executing queries
            bulk_loading_strategy: Database-specific strategy for bulk loading
            probe: Domain probe for observability (optional, defaults to DefaultMutationProbe)
        """
        self._client = client
        self._strategy = bulk_loading_strategy
        self._probe = probe or DefaultMutationProbe()

    def _sort_operations(
        self, operations: list[MutationOperation]
    ) -> list[MutationOperation]:
        """Sort operations into correct execution order.

        Order is based on referential integrity constraints that apply to
        ALL graph databases, not database-specific implementation details:
        1. DEFINE (schema definitions)
        2. DELETE edges (must delete edges before nodes)
        3. DELETE nodes
        4. CREATE nodes (must create nodes before edges)
        5. CREATE edges
        6. UPDATE (any order after creates)

        Args:
            operations: Unsorted list of operations

        Returns:
            Operations sorted in correct execution order
        """

        def sort_key(op: MutationOperation) -> tuple[int, int]:
            op_priority = {"DEFINE": 0, "DELETE": 1, "CREATE": 2, "UPDATE": 3}
            if op.op == "DELETE":
                # Delete edges before nodes
                type_priority = 0 if op.type == EntityType.EDGE else 1
            else:
                # Create/Update nodes before edges
                type_priority = 0 if op.type == EntityType.NODE else 1
            return (op_priority.get(op.op, 999), type_priority)

        return sorted(operations, key=sort_key)

    def apply_batch(
        self,
        operations: list[MutationOperation],
    ) -> MutationResult:
        """Apply a batch of mutations atomically.

        Validates operations, sorts them into correct execution order, and
        delegates execution to the bulk loading strategy.

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

        # Validate all operations before executing
        try:
            for op in operations:
                op.validate_operation()
        except Exception as e:
            self._probe.apply_batch_completed(
                total_operations=len(operations),
                total_batches=0,
                duration_ms=0.0,
                success=False,
            )
            return MutationResult(
                success=False,
                operations_applied=0,
                errors=[str(e)],
            )

        # Sort operations to respect referential integrity
        sorted_ops = self._sort_operations(operations)

        # Delegate to the bulk loading strategy (passes pre-sorted operations)
        return self._strategy.apply_batch(
            client=self._client,
            operations=sorted_ops,
            probe=self._probe,
            graph_name=self._client.graph_name,
        )
