"""Unit tests for AgeGraphClient.

These tests use mocks to test the client logic without requiring a database.
"""

import pytest

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.database.exceptions import ConnectionError


class TestAgeGraphClientInit:
    """Tests for client initialization."""

    def test_client_initializes_with_settings(self, mock_db_settings):
        """Client should initialize with provided settings."""
        client = AgeGraphClient(mock_db_settings)

        assert client.graph_name == "test_graph"
        assert client.is_connected() is False


class TestConnectionState:
    """Tests for connection state management."""

    def test_is_connected_returns_false_when_not_connected(self, mock_db_settings):
        """Client should report not connected before connect() is called."""
        client = AgeGraphClient(mock_db_settings)

        assert client.is_connected() is False

    def test_verify_connection_returns_false_when_not_connected(self, mock_db_settings):
        """Verification should return False when not connected."""
        client = AgeGraphClient(mock_db_settings)

        assert client.verify_connection() is False

    def test_execute_cypher_raises_when_not_connected(self, mock_db_settings):
        """Should raise ConnectionError when executing without connection."""
        client = AgeGraphClient(mock_db_settings)

        with pytest.raises(ConnectionError):
            client.execute_cypher("MATCH (n) RETURN n")


class TestCypherSqlWrapping:
    """Tests for Cypher query SQL wrapping logic."""

    def test_build_cypher_sql_wraps_query(self, mock_db_settings):
        """Should wrap Cypher query in AGE SQL format."""
        client = AgeGraphClient(mock_db_settings)

        sql = client._build_cypher_sql("MATCH (n) RETURN n")

        assert "cypher(" in sql
        assert "MATCH (n) RETURN n" in sql
        assert "agtype" in sql

    def test_build_cypher_sql_includes_graph_name_placeholder(self, mock_db_settings):
        """SQL should include placeholder for graph name parameter."""
        client = AgeGraphClient(mock_db_settings)

        sql = client._build_cypher_sql("CREATE (n:Node)")

        # Should use parameter placeholder for graph name
        assert "%s" in sql or "?" in sql or client.graph_name in sql
