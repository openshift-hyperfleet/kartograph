"""Database connection management for Apache AGE/PostgreSQL.

This module provides connection factory capabilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg2

from infrastructure.database.exceptions import ConnectionError
from infrastructure.observability.probes import (
    ConnectionProbe,
    DefaultConnectionProbe,
)

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PsycopgConnection

    from infrastructure.settings import DatabaseSettings


class ConnectionFactory:
    """Factory for creating and managing PostgreSQL/AGE connections.

    Handles connection creation and AGE extension setup.
    Connection pooling can be added in future iterations.
    """

    def __init__(
        self,
        settings: DatabaseSettings,
        probe: ConnectionProbe | None = None,
    ):
        self._settings = settings
        self._connection: PsycopgConnection | None = None
        self._probe = probe or DefaultConnectionProbe()

    def create_connection(self) -> PsycopgConnection:
        """Create a new database connection with AGE extension configured.

        Returns:
            A configured psycopg2 connection with AGE loaded.

        Raises:
            ConnectionError: If connection cannot be established.
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
            raise ConnectionError(f"Failed to connect to database: {e}") from e

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
        """Get an existing connection or create a new one.

        For tracer bullet simplicity, this maintains a single connection.
        Connection pooling will be added in future iterations (TODO).
        """
        if self._connection is None or self._connection.closed:
            self._connection = self.create_connection()
        return self._connection

    def close_connection(self) -> None:
        """Close the current connection if open."""
        if self._connection is not None and not self._connection.closed:
            self._connection.close()
            self._connection = None
            self._probe.connection_closed()
