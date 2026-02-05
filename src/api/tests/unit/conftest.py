"""Unit test fixtures with mocked dependencies."""

import pytest


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
