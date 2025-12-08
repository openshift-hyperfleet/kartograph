"""Unit test fixtures with mocked dependencies."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_db_settings():
    """Provide test database settings."""
    from infrastructure.settings import DatabaseSettings

    return DatabaseSettings(
        host="testhost",
        port=5432,
        database="testdb",
        username="testuser",
        password="testpass",
        graph_name="test_graph",
    )


@pytest.fixture
def mock_psycopg2_connection():
    """Provide a mocked psycopg2 connection."""
    conn = MagicMock()
    conn.closed = False

    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = (1,)

    # Set up context manager
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor

    return conn, cursor
