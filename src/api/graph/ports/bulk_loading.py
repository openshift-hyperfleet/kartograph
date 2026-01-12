"""Bulk loading strategy protocols for the Graph bounded context.

These protocols enable database-specific bulk loading optimizations while
maintaining a common interface for the MutationApplier.

The strategy pattern allows different graph databases to use their optimal
bulk loading approaches:
- Apache AGE: PostgreSQL COPY to staging tables + Cypher MERGE
- Neo4j (future): Large UNWIND batches (10K-50K) with CALL IN TRANSACTIONS
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from graph.domain.value_objects import MutationOperation, MutationResult
    from graph.ports.observability import MutationProbe
    from graph.ports.protocols import GraphClientProtocol


class BulkLoadingStrategy(Protocol):
    """Protocol for database-specific bulk loading strategies.

    Implementations should optimize for their target database's strengths.
    For example, Apache AGE benefits from PostgreSQL's COPY protocol,
    while Neo4j handles UNWIND natively at high throughput.
    """

    def apply_batch(
        self,
        client: GraphClientProtocol,
        operations: list[MutationOperation],
        probe: MutationProbe,
        graph_name: str,
    ) -> MutationResult:
        """Apply a batch of mutations using database-optimized bulk loading.

        Args:
            client: Graph database client for executing queries
            operations: List of mutation operations to apply (pre-sorted)
            probe: Domain probe for observability
            graph_name: Name of the graph being operated on

        Returns:
            MutationResult with success status and operation count
        """
        ...


class RawConnectionProtocol(Protocol):
    """Protocol for accessing raw database connection for bulk operations.

    This protocol is separate from GraphClientProtocol because direct
    connection access is only needed for specific bulk loading operations
    like PostgreSQL COPY.

    Warning: Use with caution. Direct connection access bypasses normal
    query execution paths and security wrappers.
    """

    @property
    def raw_connection(self) -> Any:
        """Access the underlying database connection.

        For psycopg2, this returns the connection object directly.

        Returns:
            The raw database connection object.
        """
        ...
