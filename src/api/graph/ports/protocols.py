"""Database connection protocols for the Graph bounded context.

These protocols enable dependency inversion, allowing the domain layer
to depend on abstractions rather than concrete implementations.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Protocol, Sequence, Union

from age.models import Edge, Path, Vertex  # type: ignore

from graph.domain.value_objects import EdgeRecord, EntityType, NodeRecord

if TYPE_CHECKING:
    from psycopg2.extensions import cursor as PsycopgCursor


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


@dataclass(frozen=True)
class NodeNeighborsResult:
    """Container for a node neighbors query result."""

    central_node: NodeRecord
    nodes: Sequence[NodeRecord]
    edges: Sequence[EdgeRecord]


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

    def execute_sql(self, sql: str) -> None:
        """Execute raw SQL (not Cypher) within the transaction.

        This is used for PostgreSQL commands like SET LOCAL that need to
        run directly on the connection, not wrapped in the cypher() function.

        Args:
            sql: Raw SQL statement to execute.
        """
        ...

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
        """Execute a Cypher query in autocommit mode.

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

    Note: For index management, see GraphIndexingProtocol which is
    implemented by database-specific clients like AgeGraphClient.
    """

    @property
    def graph_name(self) -> str:
        """The name of the graph being operated on."""
        ...

    @property
    def raw_connection(self) -> Any:
        """Get raw database connection for bulk operations like COPY.

        Warning: Use with caution. Direct connection access bypasses
        normal query execution paths and security wrappers.

        Returns:
            The underlying database connection object.
        """
        ...


class TransactionalIndexingProtocol(Protocol):
    """Protocol for creating indexes within a database transaction.

    This protocol enables database-specific index creation strategies.
    Implementations provide the appropriate indexing mechanism for their
    database backend:
    - Apache AGE: BTREE/GIN indexes on PostgreSQL tables
    - Neo4j: CREATE INDEX in Cypher
    - Neptune: OpenSearch indexes

    Indexes are created transactionally when new labels are created,
    ensuring atomicity with the label creation itself.
    """

    def create_label_indexes(
        self,
        cursor: "PsycopgCursor",
        graph_name: str,
        label: str,
        entity_type: EntityType,
    ) -> int:
        """Create indexes for a newly created label within the current transaction.

        This method is called immediately after a new label (vertex or edge type)
        is created during bulk loading operations. Creating indexes within the
        same transaction ensures atomicity.

        For nodes, implementations should create indexes optimized for:
        - Fast lookups by internal ID (graphid)
        - Property-based queries
        - Logical ID lookups (properties.id)

        For edges, implementations should additionally create indexes for:
        - Start/end node traversal (start_id, end_id)

        Args:
            cursor: Database cursor within an active transaction
            graph_name: The graph/schema name
            label: The label name (must be pre-validated)
            entity_type: EntityType.NODE or EntityType.EDGE

        Returns:
            Number of indexes created

        Raises:
            ValueError: If entity_type is invalid
        """
        ...
