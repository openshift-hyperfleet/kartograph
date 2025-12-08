"""Apache AGE Graph Client implementation.

Provides the concrete implementation of graph database operations
using psycopg2-binary directly with AGE SQL wrappers.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2

from graph.infrastructure.protocols import CypherResult
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.exceptions import (
    ConnectionError,
    GraphQueryError,
    TransactionError,
)
from infrastructure.settings import DatabaseSettings

logger = logging.getLogger(__name__)


class AgeGraphClient:
    """Apache AGE implementation of the GraphClientProtocol.

    This client provides:
    - Low-level Cypher query execution
    - Transaction management
    - Connection verification

    Example:
        settings = DatabaseSettings()
        client = AgeGraphClient(settings)
        client.connect()

        result = client.execute_cypher("MATCH (n) RETURN n LIMIT 10")

        with client.transaction() as tx:
            tx.execute_cypher("CREATE (n:Person {name: 'Alice'})")
    """

    def __init__(self, settings: DatabaseSettings):
        self._settings = settings
        self._connection_factory = ConnectionFactory(settings)
        self._graph_name = settings.graph_name
        self._connected = False

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
        return self._connection_factory._connection

    def connect(self) -> None:
        """Establish connection to the graph database."""
        try:
            self._connection_factory.get_connection()
            self._ensure_graph_exists()
            self._connected = True
            logger.info(f"Connected to graph: {self._graph_name}")
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect: {e}") from e

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
                logger.info(f"Created graph: {self._graph_name}")

    def disconnect(self) -> None:
        """Close the database connection."""
        self._connection_factory.close_connection()
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
            logger.warning(f"Connection verification failed: {e}")
            return False

    def _build_cypher_sql(self, query: str) -> str:
        """Build the SQL statement for executing a Cypher query via AGE.

        AGE requires Cypher queries to be wrapped in:
        SELECT * FROM cypher('graph_name', $$ CYPHER_QUERY $$) AS (result agtype)
        """
        return f"""
            SELECT * FROM cypher('{self._graph_name}', $$ {query} $$) AS (result agtype)
        """

    def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> CypherResult:
        """Execute a Cypher query.

        Args:
            query: The Cypher query string (without the cypher() wrapper).
            parameters: Optional query parameters (for future use).

        Returns:
            CypherResult containing the query results.

        Raises:
            GraphQueryError: If query execution fails.
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to database")

        try:
            with self._connection.cursor() as cursor:
                sql = self._build_cypher_sql(query)
                cursor.execute(sql)

                rows = cursor.fetchall()
                self._connection.commit()

                return CypherResult(
                    rows=tuple(rows),
                    row_count=len(rows),
                )

        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Query execution failed: {e}", extra={"query": query})
            raise GraphQueryError(f"Query execution failed: {e}", query=query) from e

    @contextmanager
    def transaction(self) -> Iterator[_AgeTransaction]:
        """Create a transaction context for atomic operations.

        Usage:
            with client.transaction() as tx:
                tx.execute_cypher("CREATE ...")
                tx.execute_cypher("CREATE ...")
                # Auto-commits on success, rolls back on exception
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to database")

        tx = _AgeTransaction(self._connection, self._graph_name)
        try:
            yield tx
            tx.commit()
        except Exception:
            tx.rollback()
            raise


class _AgeTransaction:
    """Internal transaction implementation for AgeGraphClient."""

    def __init__(self, connection, graph_name: str):
        self._connection = connection
        self._graph_name = graph_name
        self._committed = False
        self._rolled_back = False

    def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> CypherResult:
        """Execute a Cypher query within the transaction."""
        if self._committed or self._rolled_back:
            raise TransactionError("Transaction already finalized")

        try:
            with self._connection.cursor() as cursor:
                sql = f"""
                    SELECT * FROM cypher('{self._graph_name}', $$ {query} $$) AS (result agtype)
                """
                cursor.execute(sql)
                rows = cursor.fetchall()

                return CypherResult(
                    rows=tuple(rows),
                    row_count=len(rows),
                )

        except psycopg2.Error as e:
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
