"""Apache AGE Graph Client implementation.

Provides the concrete implementation of graph database operations
using psycopg2 with Apache AGE extension and AGType parsing.
"""

from __future__ import annotations

import secrets
import string
import typing
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

import age  # type: ignore
import psycopg2

from graph.infrastructure.exceptions import InsecureCypherQueryError
from graph.infrastructure.observability import (
    DefaultGraphClientProbe,
    GraphClientProbe,
)
from graph.ports.protocols import CypherResult, GraphClientProtocol
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.exceptions import (
    DatabaseConnectionError,
    GraphQueryError,
    TransactionError,
)
from infrastructure.settings import DatabaseSettings

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PsycopgConnection


class AgeGraphClient(GraphClientProtocol):
    """Apache AGE implementation of the GraphClientProtocol.

    This client provides:
    - Low-level Cypher query execution
    - Transaction management
    - Connection verification
    - Automatic index creation for label id properties

    Example:
        settings = DatabaseSettings()
        client = AgeGraphClient(settings)
        client.connect()

        result = client.execute_cypher("MATCH (n) RETURN n LIMIT 10")

        with client.transaction() as tx:
            tx.execute_cypher("CREATE (n:Person {name: 'Alice'})")
    """

    def __init__(
        self,
        settings: DatabaseSettings,
        connection_factory: ConnectionFactory | None = None,
        probe: GraphClientProbe | None = None,
    ):
        """Initialize the AGE graph client.

        Args:
            settings: Database connection settings
            connection_factory: Optional connection factory (required for pooled mode)
            probe: Optional observability probe
        """
        self._settings = settings
        self._connection_factory = connection_factory
        self._graph_name = settings.graph_name
        self._connected = False
        self._current_connection: PsycopgConnection | None = None
        self._probe = probe or DefaultGraphClientProbe()
        # Track labels that have been indexed in this session
        self._indexed_labels: set[str] = set()

    @property
    def graph_name(self) -> str:
        """The name of the graph being operated on."""
        return self._graph_name

    def is_connected(self) -> bool:
        """Check if the connection is active and valid."""
        return self._connected and self._connection is not None

    @property
    def _connection(self):
        """Get the underlying psycopg2 connection."""
        if self._current_connection is None:
            raise ValueError("No active connection. Call connect() first.")
        return self._current_connection

    @property
    def raw_connection(self):
        """Get raw database connection for bulk operations like COPY.

        Warning: Use with caution. Direct connection access bypasses
        normal query execution paths and security wrappers.

        Returns:
            The underlying psycopg2 connection object.
        """
        return self._connection

    def connect(self) -> None:
        """Establish connection to the graph database."""
        if self._connection_factory is None:
            raise ValueError(
                "ConnectionFactory required. Pass connection_factory parameter to __init__."
            )

        try:
            self._current_connection = self._connection_factory.get_connection()
            self._ensure_graph_exists()
            # Register AGType parser for automatic conversion of Vertex, Edge, Path objects
            age.setUpAge(self._current_connection, self._graph_name)
            self._connected = True
            self._probe.connected_to_graph(self._graph_name)
        except Exception as e:
            self._connected = False
            raise DatabaseConnectionError(f"Failed to connect: {e}") from e

    def _ensure_graph_exists(self) -> None:
        """Ensure the graph exists, creating it if necessary."""
        with self._connection.cursor() as cursor:
            # Check if graph exists
            cursor.execute(
                "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
                (self._graph_name,),
            )
            if cursor.fetchone() is None:
                # Create the graph
                cursor.execute(
                    "SELECT ag_catalog.create_graph(%s)",
                    (self._graph_name,),
                )
                self._connection.commit()
                self._probe.graph_created(self._graph_name)

    def ensure_label_index(self, label: str) -> bool:
        """Ensure a GIN index exists on properties for a label.

        Apache AGE stores graph data in PostgreSQL tables with properties
        stored as agtype (not JSONB). Without indexes, MATCH operations
        do full table scans which is extremely slow for large graphs.

        This creates a GIN index on the properties column for fast lookups
        on any property including 'id'. GIN indexes are the recommended
        approach for AGE agtype properties.

        Args:
            label: The label name (e.g., 'Person', 'documentationmodule')

        Returns:
            True if index was created, False if it already existed

        Note:
            Labels are case-sensitive in AGE. The internal table name
            uses the exact label casing from the first CREATE.

        References:
            - https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/generative-ai-age-performance
            - https://github.com/apache/age/issues/920
        """
        if not self.is_connected():
            raise DatabaseConnectionError("Not connected to database")

        # Skip if already indexed this session
        if label in self._indexed_labels:
            return False

        # Sanitize label name for SQL identifier (prevent SQL injection)
        # AGE labels can only contain alphanumeric and underscore
        if not label.replace("_", "").isalnum():
            raise ValueError(f"Invalid label name: {label}")

        # Index name format: idx_{graph}_{label}_props_gin
        index_name = f"idx_{self._graph_name}_{label}_props_gin"

        with self._connection.cursor() as cursor:
            # Check if index already exists
            cursor.execute(
                """
                SELECT 1 FROM pg_indexes
                WHERE schemaname = %s AND indexname = %s
                """,
                (self._graph_name, index_name),
            )
            if cursor.fetchone() is not None:
                self._indexed_labels.add(label)
                return False

            # Check if the label table exists
            cursor.execute(
                """
                SELECT 1 FROM ag_catalog.ag_label
                WHERE graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = %s)
                AND name = %s
                """,
                (self._graph_name, label),
            )
            if cursor.fetchone() is None:
                # Label doesn't exist yet, will be created on first use
                return False

            # Create GIN index on properties column
            # GIN indexes work with agtype and support efficient key-value lookups
            # Note: We use format() here because index/table names can't be parameterized
            cursor.execute(
                f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                f'ON "{self._graph_name}"."{label}" USING GIN (properties)'
            )
            self._connection.commit()

            self._indexed_labels.add(label)
            self._probe.query_executed(query=f"CREATE INDEX {index_name}", row_count=0)
            return True

    def ensure_labels_indexed(self, labels: set[str]) -> int:
        """Ensure indexes exist for multiple labels.

        Args:
            labels: Set of label names to index

        Returns:
            Number of new indexes created
        """
        created = 0
        for label in labels:
            if self.ensure_label_index(label):
                created += 1
        return created

    def ensure_label_indexes(self, label: str, kind: str = "v") -> int:
        """Ensure all recommended indexes exist for a label.

        Creates comprehensive indexes following Microsoft Azure best practices:
        - BTREE on id column (graphid) for fast vertex/edge lookups
        - GIN on properties column for property-based queries
        - BTREE on properties.id for logical ID lookups via agtype_access_operator
        - For edges: BTREE on start_id and end_id for join performance

        Args:
            label: The label name (e.g., 'person', 'knows')
            kind: 'v' for vertex labels, 'e' for edge labels

        Returns:
            Number of new indexes created

        Raises:
            DatabaseConnectionError: If not connected to database
            ValueError: If label name is invalid

        References:
            - https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/generative-ai-age-performance
            - https://github.com/apache/age/issues/2176
        """
        if not self.is_connected():
            raise DatabaseConnectionError("Not connected to database")

        # Validate label name (prevent SQL injection)
        if not label.replace("_", "").isalnum():
            raise ValueError(f"Invalid label name: {label}")

        with self._connection.cursor() as cursor:
            # Check if the label table exists
            cursor.execute(
                """
                SELECT 1 FROM ag_catalog.ag_label
                WHERE graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = %s)
                AND name = %s
                """,
                (self._graph_name, label),
            )
            if cursor.fetchone() is None:
                # Label doesn't exist yet
                return 0

            # Define indexes to create
            indexes = []

            # BTREE on id column (graphid) - critical for all labels
            indexes.append(
                {
                    "name": f"idx_{self._graph_name}_{label}_id_btree",
                    "sql": f'CREATE INDEX IF NOT EXISTS "idx_{self._graph_name}_{label}_id_btree" '
                    f'ON "{self._graph_name}"."{label}" USING BTREE (id)',
                }
            )

            # GIN on properties column - for property-based queries
            indexes.append(
                {
                    "name": f"idx_{self._graph_name}_{label}_props_gin",
                    "sql": f'CREATE INDEX IF NOT EXISTS "idx_{self._graph_name}_{label}_props_gin" '
                    f'ON "{self._graph_name}"."{label}" USING GIN (properties)',
                }
            )

            # BTREE on properties.id - for logical ID lookups
            # Uses agtype_access_operator for efficient access to specific property
            indexes.append(
                {
                    "name": f"idx_{self._graph_name}_{label}_prop_id_btree",
                    "sql": f'CREATE INDEX IF NOT EXISTS "idx_{self._graph_name}_{label}_prop_id_btree" '
                    f'ON "{self._graph_name}"."{label}" USING BTREE ('
                    f"agtype_access_operator(VARIADIC ARRAY[properties, '\"id\"'::agtype]))",
                }
            )

            # Edge-specific indexes
            if kind == "e":
                # BTREE on start_id - for join performance
                indexes.append(
                    {
                        "name": f"idx_{self._graph_name}_{label}_start_id_btree",
                        "sql": f'CREATE INDEX IF NOT EXISTS "idx_{self._graph_name}_{label}_start_id_btree" '
                        f'ON "{self._graph_name}"."{label}" USING BTREE (start_id)',
                    }
                )
                # BTREE on end_id - for join performance
                indexes.append(
                    {
                        "name": f"idx_{self._graph_name}_{label}_end_id_btree",
                        "sql": f'CREATE INDEX IF NOT EXISTS "idx_{self._graph_name}_{label}_end_id_btree" '
                        f'ON "{self._graph_name}"."{label}" USING BTREE (end_id)',
                    }
                )

            created = 0
            for idx in indexes:
                # Check if index already exists
                cursor.execute(
                    """
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname = %s AND indexname = %s
                    """,
                    (self._graph_name, idx["name"]),
                )
                if cursor.fetchone() is not None:
                    continue

                # Create the index
                cursor.execute(idx["sql"])
                created += 1
                self._probe.query_executed(
                    query=f"CREATE INDEX {idx['name']}", row_count=0
                )

            if created > 0:
                self._connection.commit()

            # Track that this label has been fully indexed
            self._indexed_labels.add(label)

            return created

    def ensure_all_labels_indexed(self) -> int:
        """Ensure indexes exist for ALL labels in the graph.

        Creates comprehensive indexes for both vertex and edge labels.
        This is critical for performance - without indexes, MATCH operations
        do full table scans which is extremely slow for large graphs.

        For vertex labels:
        - BTREE on id (graphid column)
        - GIN on properties
        - BTREE on properties.id (logical ID)

        For edge labels:
        - BTREE on id (graphid column)
        - BTREE on start_id and end_id (for joins)
        - GIN on properties
        - BTREE on properties.id (logical ID)

        Returns:
            Number of new indexes created
        """
        if not self.is_connected():
            raise DatabaseConnectionError("Not connected to database")

        with self._connection.cursor() as cursor:
            # Get all labels in this graph with their kind (vertex or edge)
            cursor.execute(
                """
                SELECT name, kind FROM ag_catalog.ag_label
                WHERE graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = %s)
                AND name NOT LIKE '_ag_label%%'
                """,
                (self._graph_name,),
            )
            labels = [(row[0], row[1]) for row in cursor.fetchall()]

        total_created = 0
        for label_name, kind in labels:
            created = self.ensure_label_indexes(label_name, kind=kind)
            total_created += created

        return total_created

    def disconnect(self) -> None:
        """Close the database connection and return it to the pool."""
        if (
            self._current_connection is not None
            and self._connection_factory is not None
        ):
            self._connection_factory.return_connection(self._current_connection)
            self._current_connection = None
        self._connected = False

    def verify_connection(self) -> bool:
        """Verify the connection is working by executing a simple query.

        Returns:
            True if connection is healthy, False otherwise.
        """
        if not self.is_connected():
            return False

        try:
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None and result[0] == 1
        except Exception as e:
            self._probe.connection_verification_failed(e)
            return False

    def _generate_nonce(self) -> str:
        """
        Generate a random 64 character string for use as a nonce
        when generating a unique tag for quoting cypher queries in Apache AGE.
        """
        return "".join(secrets.choice(string.ascii_letters) for _ in range(64))

    def build_secure_cypher_sql(
        self,
        graph_name: str,
        query: str,
        nonce_generator: typing.Optional[typing.Callable[[], str]] = None,
    ) -> str:
        """Build the SQL statement for executing a Cypher query via AGE.

        AGE requires Cypher queries to be wrapped in:
        SELECT * FROM cypher('graph_name', <nonce> CYPHER_QUERY <nonce> AS (result agtype)

        As a security consideration, a unique cypher query tag (as opposed to the default $$) is
        generated for each query to reduce the risk of SQL injection. If the unique tag is found in the query,
        an InsecureCypherQueryError is raised. A `nonce_generator` may be passed that will be used
        to generate the random tag body (value between $$). The nonce_generator should return a random string.
        If none is provided, the AgeGraphClient._generate_nonce method will be used.

        Note that there is a hard-coded return type of (result agtype), which means
        the query _must_ be written such that it returns a single object (which may contain multiple items.)
        """

        nonce_generator = nonce_generator if nonce_generator else self._generate_nonce

        nonce = nonce_generator()

        if nonce in query:
            raise InsecureCypherQueryError(
                message="Unique nonce detected in cypher query.", query=query
            )

        # Cypher queries can be denoted by a custom tag by placing a string
        # between the two $'s.
        tag = f"${nonce}$"

        return f"""\
SELECT * FROM cypher('{graph_name}', {tag} {query} {tag}) AS (result agtype)\
"""

    def _build_cypher_sql(self, query: str) -> str:
        return self.build_secure_cypher_sql(graph_name=self.graph_name, query=query)

    def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> CypherResult:
        """Execute a Cypher query in auto-commit mode.

        This method executes a single query and immediately commits it.
        Each call to this method results in a separate database transaction.

        Use this for:
            - Single, independent queries
            - Read-only operations
            - Simple writes where atomicity across multiple operations is not needed

        For multiple related operations that must succeed/fail together,
        use the transaction() context manager instead.

        Args:
            query: The Cypher query string (without the cypher() wrapper).
            parameters: Optional query parameters (for future use).

        Returns:
            CypherResult containing the query results.

        Raises:
            DatabaseConnectionError: If not connected to database.
            GraphQueryError: If query execution fails.
        """
        if not self.is_connected():
            raise DatabaseConnectionError("Not connected to database")

        try:
            with self._connection.cursor() as cursor:
                sql = self._build_cypher_sql(query)
                cursor.execute(sql)

                rows = cursor.fetchall()
                self._connection.commit()

                result = CypherResult(
                    rows=tuple(rows),
                    row_count=len(rows),
                )

                # Record successful query execution
                self._probe.query_executed(query=query, row_count=result.row_count)

                return result

        except psycopg2.Error as e:
            self._connection.rollback()
            self._probe.query_failed(query=query, error=e)
            raise GraphQueryError(f"Query execution failed: {e}", query=query) from e

    @contextmanager
    def transaction(self) -> Iterator[_AgeTransaction]:
        """Create a transaction context for atomic operations.

        All queries executed within the transaction context will be committed
        together when the context exits successfully, or rolled back if any
        exception occurs. This ensures atomicity across multiple operations.

        Use this for:
            - Creating multiple related entities that must exist together
            - Batch operations from mutation logs
            - Any operations where partial completion would leave inconsistent state

        For single, independent queries, use execute_cypher() instead.

        Usage:
            with client.transaction() as tx:
                tx.execute_cypher("CREATE (p:Person {name: 'Alice'})")
                tx.execute_cypher("CREATE (p:Person {name: 'Bob'})")
                tx.execute_cypher("CREATE (:Person {name: 'Alice'})-[:KNOWS]->(:Person {name: 'Bob'})")
                # All queries commit together on success, or all rollback on error

        Raises:
            DatabaseConnectionError: If not connected to database.
        """
        if not self.is_connected():
            raise DatabaseConnectionError("Not connected to database")

        self._probe.transaction_started()
        tx = _AgeTransaction(
            connection=self._connection,
            graph_name=self._graph_name,
            probe=self._probe,
            sql_builder=self._build_cypher_sql,
        )
        try:
            yield tx
            tx.commit()
            self._probe.transaction_committed()
        except Exception:
            tx.rollback()
            self._probe.transaction_rolled_back()
            raise


class _AgeTransaction:
    """Internal transaction implementation for AgeGraphClient.

    This class is not intended to be instantiated directly. Use
    AgeGraphClient.transaction() context manager instead.
    """

    def __init__(
        self,
        connection: PsycopgConnection,
        graph_name: str,
        probe: GraphClientProbe,
        sql_builder: typing.Callable[[str], str],
    ):
        self._connection = connection
        self._graph_name = graph_name
        self._probe = probe
        self._sql_builder = sql_builder
        self._committed = False
        self._rolled_back = False

    def execute_sql(self, sql: str) -> None:
        """Execute raw SQL (not Cypher) within the transaction.

        This is used for PostgreSQL commands like SET LOCAL that need to
        run directly on the connection, not wrapped in the cypher() function.

        Args:
            sql: Raw SQL statement to execute.

        Raises:
            TransactionError: If transaction is already finalized.
            GraphQueryError: If SQL execution fails.
        """
        if self._committed or self._rolled_back:
            raise TransactionError("Transaction already finalized")

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(sql)
        except psycopg2.Error as e:
            raise GraphQueryError(f"SQL execution failed: {e}", query=sql) from e

    def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> CypherResult:
        """Execute a Cypher query within the transaction context.

        Queries are NOT automatically committed. The transaction will be committed
        when the context manager exits successfully, or rolled back if an exception
        occurs.

        This method should only be called within the AgeGraphClient.transaction()
        context manager, which handles commit/rollback.

        Args:
            query: The Cypher query string (without the cypher() wrapper).
            parameters: Optional query parameters (for future use).

        Returns:
            CypherResult containing the query results.

        Raises:
            TransactionError: If transaction is already finalized.
            GraphQueryError: If query execution fails.
        """
        if self._committed or self._rolled_back:
            raise TransactionError("Transaction already finalized")

        try:
            with self._connection.cursor() as cursor:
                sql = self._sql_builder(query)

                cursor.execute(sql)
                rows = cursor.fetchall()

                result = CypherResult(
                    rows=tuple(rows),
                    row_count=len(rows),
                )

                # Record successful query execution in transaction
                self._probe.query_executed(query=query, row_count=result.row_count)

                return result

        except psycopg2.Error as e:
            self._probe.query_failed(query=query, error=e)
            raise GraphQueryError(f"Transaction query failed: {e}", query=query) from e

    def commit(self) -> None:
        """Commit the transaction."""
        if self._rolled_back:
            raise TransactionError("Cannot commit a rolled-back transaction")
        if not self._committed:
            self._connection.commit()
            self._committed = True

    def rollback(self) -> None:
        """Rollback the transaction."""
        if self._committed:
            raise TransactionError("Cannot rollback a committed transaction")
        if not self._rolled_back:
            self._connection.rollback()
            self._rolled_back = True
