"""Database connection protocols for the Graph bounded context.

These protocols enable dependency inversion, allowing the domain layer
to depend on abstractions rather than concrete implementations.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Protocol, Sequence, Union

from age.models import Edge, Path, Vertex


@dataclass(frozen=True)
class CypherResult:
    """Container for Cypher query results.

    Results contain tuples where each element can be:
    - Vertex: A graph node with id, label, and properties
    - Edge: A graph relationship with id, label, start_id, end_id, and properties
    - Path: A graph path containing vertices and edges
    - Any: Other AGType values (scalars, lists, etc.)
    """

    rows: Sequence[tuple[Union[Vertex, Edge, Path, Any], ...]]
    row_count: int


class GraphConnectionProtocol(Protocol):
    """Protocol for low-level graph database connections.

    This is the foundational interface that higher-level abstractions
    (repositories, query services) will be built upon.
    """

    def is_connected(self) -> bool:
        """Check if the connection is active and valid."""
        ...

    def connect(self) -> None:
        """Establish connection to the graph database."""
        ...

    def disconnect(self) -> None:
        """Close the database connection."""
        ...

    def verify_connection(self) -> bool:
        """Verify the connection is working by executing a simple query.

        Returns:
            True if connection is healthy, False otherwise.
        """
        ...


class GraphTransactionProtocol(Protocol):
    """Protocol for graph database transactions."""

    def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> CypherResult:
        """Execute a Cypher query within the transaction."""
        ...

    def commit(self) -> None:
        """Commit the transaction."""
        ...

    def rollback(self) -> None:
        """Rollback the transaction."""
        ...


class GraphQueryExecutorProtocol(Protocol):
    """Protocol for executing Cypher queries against the graph database."""

    def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> CypherResult:
        """Execute a Cypher query.

        Args:
            query: The Cypher query string (without the cypher() wrapper).
            parameters: Optional query parameters for parameterized queries.

        Returns:
            CypherResult containing the query results.

        Raises:
            GraphQueryError: If query execution fails.
        """
        ...

    @contextmanager
    def transaction(self) -> Iterator[GraphTransactionProtocol]:
        """Create a transaction context for atomic operations.

        Usage:
            with client.transaction() as tx:
                tx.execute_cypher("CREATE ...")
                tx.execute_cypher("CREATE ...")
                # Auto-commits on success, rolls back on exception
        """
        ...


class GraphClientProtocol(
    GraphConnectionProtocol, GraphQueryExecutorProtocol, Protocol
):
    """Combined protocol for full graph client capabilities.

    This is the primary interface that will be injected into services
    and repositories within the Graph bounded context.
    """

    @property
    def graph_name(self) -> str:
        """The name of the graph being operated on."""
        ...
