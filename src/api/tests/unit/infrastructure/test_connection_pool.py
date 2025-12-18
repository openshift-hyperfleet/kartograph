"""Unit tests for ConnectionPool."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

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
        pool_min_connections=2,
        pool_max_connections=5,
    )


class TestConnectionPoolInit:
    """Tests for ConnectionPool initialization."""

    def test_pool_initializes_with_settings(self, mock_db_settings):
        """Should create ThreadedConnectionPool on init."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ) as mock_pool_class:
            pool = ConnectionPool(mock_db_settings)

            mock_pool_class.assert_called_once_with(
                minconn=2,
                maxconn=5,
                host="localhost",
                port=5432,
                dbname="test_db",
                user="test_user",
                password="test_pass",
            )
            assert pool._pool is not None

    def test_pool_stores_settings(self, mock_db_settings):
        """Should store settings reference."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ):
            pool = ConnectionPool(mock_db_settings)
            assert pool._settings == mock_db_settings


class TestGetConnection:
    """Tests for get_connection method."""

    def test_gets_connection_from_pool(self, mock_db_settings):
        """Should get connection from pool."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ) as mock_pool_class:
            mock_pool_instance = MagicMock()
            mock_conn = MagicMock()
            mock_pool_instance.getconn.return_value = mock_conn
            mock_pool_class.return_value = mock_pool_instance

            pool = ConnectionPool(mock_db_settings)
            conn = pool.get_connection()

            mock_pool_instance.getconn.assert_called_once()
            assert conn == mock_conn

    def test_calls_ensure_age_setup_on_connection(self, mock_db_settings):
        """Should ensure AGE setup on connection."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ) as mock_pool_class:
            mock_pool_instance = MagicMock()
            mock_conn = MagicMock()
            mock_pool_instance.getconn.return_value = mock_conn
            mock_pool_class.return_value = mock_pool_instance

            pool = ConnectionPool(mock_db_settings)

            with patch.object(pool, "_ensure_age_setup") as mock_ensure:
                pool.get_connection()
                mock_ensure.assert_called_once_with(mock_conn)


class TestReturnConnection:
    """Tests for return_connection method."""

    def test_returns_connection_to_pool(self, mock_db_settings):
        """Should return connection to pool."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ) as mock_pool_class:
            mock_pool_instance = MagicMock()
            mock_conn = MagicMock()
            mock_pool_class.return_value = mock_pool_instance

            pool = ConnectionPool(mock_db_settings)
            pool.return_connection(mock_conn)

            mock_pool_instance.putconn.assert_called_once_with(mock_conn)


class TestCloseAll:
    """Tests for close_all method."""

    def test_closes_all_connections(self, mock_db_settings):
        """Should close all connections in pool."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ) as mock_pool_class:
            mock_pool_instance = MagicMock()
            mock_pool_class.return_value = mock_pool_instance

            pool = ConnectionPool(mock_db_settings)
            pool.close_all()

            mock_pool_instance.closeall.assert_called_once()

    def test_nullifies_pool_after_close(self, mock_db_settings):
        """Should set _pool to None after closing."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ) as mock_pool_class:
            mock_pool_instance = MagicMock()
            mock_pool_class.return_value = mock_pool_instance

            pool = ConnectionPool(mock_db_settings)
            pool.close_all()

            assert pool._pool is None


class TestEnsureAgeSetup:
    """Tests for _ensure_age_setup method."""

    def test_skips_setup_if_already_configured(self, mock_db_settings):
        """Should skip setup if connection ID already tracked."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ):
            pool = ConnectionPool(mock_db_settings)

            mock_conn = MagicMock()
            # Mark as already setup
            pool._age_setup_connections.add(id(mock_conn))

            with patch.object(pool, "_setup_age") as mock_setup:
                pool._ensure_age_setup(mock_conn)
                mock_setup.assert_not_called()

    def test_calls_setup_and_marks_connection(self, mock_db_settings):
        """Should call setup and track connection ID."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ):
            pool = ConnectionPool(mock_db_settings)

            mock_conn = MagicMock()
            conn_id = id(mock_conn)

            with patch.object(pool, "_setup_age") as mock_setup:
                pool._ensure_age_setup(mock_conn)
                mock_setup.assert_called_once_with(mock_conn)
                assert conn_id in pool._age_setup_connections


class TestSetupAge:
    """Tests for _setup_age method."""

    def test_loads_age_extension(self, mock_db_settings):
        """Should execute LOAD and SET search_path."""
        with patch(
            "infrastructure.database.connection_pool.psycopg2_pool.ThreadedConnectionPool"
        ):
            pool = ConnectionPool(mock_db_settings)

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(
                return_value=mock_cursor
            )
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

            pool._setup_age(mock_conn)

            # Verify LOAD and SET were called
            assert mock_cursor.execute.call_count == 2
            calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
            assert any("LOAD 'age'" in call for call in calls)
            assert any("SET search_path" in call for call in calls)

            # Verify commit called
            mock_conn.commit.assert_called_once()
