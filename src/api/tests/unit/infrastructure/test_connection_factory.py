"""Unit tests for ConnectionFactory with pool support."""

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings


@pytest.fixture
def mock_db_settings():
    """Create mock database settings."""
    return DatabaseSettings(
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user",
        password=SecretStr("test_pass"),
        graph_name="test_graph",
    )


@pytest.fixture
def mock_pool():
    """Create mock connection pool."""
    return MagicMock(spec=ConnectionPool)


class TestConnectionFactory:
    """Tests for ConnectionFactory."""

    def test_factory_requires_pool(self, mock_db_settings):
        """ConnectionFactory requires a pool parameter."""
        mock_pool = MagicMock(spec=ConnectionPool)
        factory = ConnectionFactory(mock_db_settings, pool=mock_pool)
        assert factory._pool is mock_pool

    def test_gets_connection_from_pool(self, mock_db_settings, mock_pool):
        """Should delegate to pool.get_connection()."""
        mock_conn = MagicMock()
        mock_pool.get_connection.return_value = mock_conn

        factory = ConnectionFactory(mock_db_settings, pool=mock_pool)
        conn = factory.get_connection()

        assert conn == mock_conn
        mock_pool.get_connection.assert_called_once()

    def test_returns_connection_to_pool(self, mock_db_settings, mock_pool):
        """Should delegate to pool.return_connection()."""
        mock_conn = MagicMock()

        factory = ConnectionFactory(mock_db_settings, pool=mock_pool)
        factory.return_connection(mock_conn)

        mock_pool.return_connection.assert_called_once_with(mock_conn)
