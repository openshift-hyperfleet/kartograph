"""Connection pool for Apache AGE/PostgreSQL.

This module provides connection pooling using psycopg2.pool.ThreadedConnectionPool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg2
from psycopg2 import pool as psycopg2_pool

from infrastructure.database.exceptions import DatabaseConnectionError
from infrastructure.observability.probes import (
    ConnectionProbe,
    DefaultConnectionProbe,
)

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PsycopgConnection

    from infrastructure.settings import DatabaseSettings


class ConnectionPool:
    """Thread-safe connection pool for PostgreSQL/AGE.

    Wraps psycopg2.pool.ThreadedConnectionPool and ensures all connections
    have the AGE extension properly configured.

    Attributes:
        _settings: Database configuration settings
        _pool: The underlying ThreadedConnectionPool instance
        _probe: Observability probe for monitoring
    """

    def __init__(
        self,
        settings: DatabaseSettings,
        probe: ConnectionProbe | None = None,
    ):
        """Initialize the connection pool.

        Args:
            settings: Database connection settings
            probe: Optional observability probe
        """
        self._settings = settings
        self._probe = probe or DefaultConnectionProbe()
        self._pool: psycopg2_pool.ThreadedConnectionPool | None = None

        if settings.pool_enabled:
            self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize the ThreadedConnectionPool."""
        try:
            self._pool = psycopg2_pool.ThreadedConnectionPool(
                minconn=self._settings.pool_min_connections,
                maxconn=self._settings.pool_max_connections,
                host=self._settings.host,
                port=self._settings.port,
                dbname=self._settings.database,
                user=self._settings.username,
                password=self._settings.password.get_secret_value(),
            )
            self._probe.pool_initialized(
                min_conn=self._settings.pool_min_connections,
                max_conn=self._settings.pool_max_connections,
            )
        except psycopg2.Error as e:
            self._probe.pool_initialization_failed(error=e)
            raise DatabaseConnectionError(
                f"Failed to initialize connection pool: {e}"
            ) from e

    def get_connection(self) -> PsycopgConnection:
        """Get a connection from the pool.

        The connection will have AGE extension configured.

        Returns:
            A configured psycopg2 connection.

        Raises:
            DatabaseConnectionError: If pool is not initialized or connection fails.
        """
        if self._pool is None:
            raise DatabaseConnectionError("Connection pool not initialized")

        try:
            conn = self._pool.getconn()
            # Setup AGE extension on first use of this connection
            self._ensure_age_setup(conn)
            self._probe.connection_acquired_from_pool()
            return conn
        except psycopg2_pool.PoolError as e:
            self._probe.pool_exhausted()
            raise DatabaseConnectionError(
                f"Pool exhausted, cannot get connection: {e}"
            ) from e

    def return_connection(self, conn: PsycopgConnection) -> None:
        """Return a connection to the pool.

        Args:
            conn: The connection to return.
        """
        if self._pool is None:
            return

        try:
            self._pool.putconn(conn)
            self._probe.connection_returned_to_pool()
        except Exception as e:
            self._probe.connection_return_failed(error=e)
            # Don't raise - connection will be discarded

    def close_all(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._probe.pool_closed()
            self._pool = None

    def _ensure_age_setup(self, conn: PsycopgConnection) -> None:
        """Ensure AGE extension is configured on the connection.

        Uses a connection-level flag to avoid redundant setup.
        """
        # Check if we've already set up AGE on this connection
        if hasattr(conn, "_kartograph_age_setup") and conn._kartograph_age_setup:
            return

        self._setup_age(conn)
        # Mark connection as configured
        conn._kartograph_age_setup = True  # type: ignore

    def _setup_age(self, conn: PsycopgConnection) -> None:
        """Set up AGE extension on the connection.

        Args:
            conn: The connection to configure
        """
        with conn.cursor() as cursor:
            cursor.execute("LOAD 'age';")
            cursor.execute('SET search_path = ag_catalog, "$user", public;')
        conn.commit()
