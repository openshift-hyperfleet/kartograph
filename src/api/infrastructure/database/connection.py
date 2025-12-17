"""Database connection management for Apache AGE/PostgreSQL.

This module provides connection factory capabilities with pool support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg2

from infrastructure.database.exceptions import DatabaseConnectionError
from infrastructure.observability.probes import (
    ConnectionProbe,
    DefaultConnectionProbe,
)

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PsycopgConnection

    from infrastructure.database.connection_pool import ConnectionPool
    from infrastructure.settings import DatabaseSettings


class ConnectionFactory:
    """Factory for managing PostgreSQL/AGE connections via pool.

    Always uses ConnectionPool for connection management.
    Tests should create small pools (e.g., min=1, max=2).
    """

    def __init__(
        self,
        settings: DatabaseSettings,
        pool: ConnectionPool,
        probe: ConnectionProbe | None = None,
    ):
        """Initialize the connection factory.

        Args:
            settings: Database connection settings
            pool: Connection pool (required)
            probe: Optional observability probe
        """
        self._settings = settings
        self._pool = pool
        self._probe = probe or DefaultConnectionProbe()

    def create_connection(self) -> PsycopgConnection:
        """Create a new database connection with AGE extension configured.

        Returns:
            A configured psycopg2 connection with AGE loaded.

        Raises:
            DatabaseConnectionError: If connection cannot be established.
        """
        try:
            conn = psycopg2.connect(
                host=self._settings.host,
                port=self._settings.port,
                dbname=self._settings.database,
                user=self._settings.username,
                password=self._settings.password.get_secret_value(),
            )

            # Set up AGE extension for this connection
            self._setup_age(conn)

            self._probe.connection_established(
                host=self._settings.host,
                database=self._settings.database,
            )

            return conn

        except psycopg2.Error as e:
            self._probe.connection_failed(
                host=self._settings.host,
                database=self._settings.database,
                error=e,
            )
            raise DatabaseConnectionError(f"Failed to connect to database: {e}") from e

    def _setup_age(self, conn: PsycopgConnection) -> None:
        """Set up AGE extension on the connection.

        Loads the AGE extension and sets the search path.
        """
        with conn.cursor() as cursor:
            # Load AGE extension
            cursor.execute("LOAD 'age';")
            # Set search path to include ag_catalog
            cursor.execute('SET search_path = ag_catalog, "$user", public;')
        conn.commit()

    def get_connection(self) -> PsycopgConnection:
        """Get a connection from the pool.

        Returns:
            A psycopg2 connection from the pool.

        Raises:
            DatabaseConnectionError: If connection cannot be obtained.
        """
        return self._pool.get_connection()

    def return_connection(self, conn: PsycopgConnection) -> None:
        """Return a connection to the pool.

        Args:
            conn: The connection to return
        """
        self._pool.return_connection(conn)
