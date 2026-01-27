"""Database connection management for Apache AGE/PostgreSQL.

This module provides connection factory capabilities with pool support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


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
