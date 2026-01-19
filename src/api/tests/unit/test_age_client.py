"""Unit tests for AgeGraphClient.

These tests use mocks to test the client logic without requiring a database.
"""

import pytest
from psycopg2 import sql

from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.cypher_utils import generate_cypher_nonce
from graph.infrastructure.exceptions import InsecureCypherQueryError
from infrastructure.database.exceptions import DatabaseConnectionError


def composable_to_string(composed: sql.Composable) -> str:
    """Convert a sql.Composable to a string for testing purposes.

    This handles sql.Composed, sql.SQL, sql.Literal, and sql.Identifier objects
    without requiring a real database connection. Uses public psycopg2 attributes.

    Args:
        composed: A psycopg2 sql.Composable object

    Returns:
        A string representation of the composed SQL
    """
    if isinstance(composed, sql.Composed):
        return "".join(composable_to_string(part) for part in composed.seq)
    elif isinstance(composed, sql.SQL):
        # Use public .string attribute
        return composed.string
    elif isinstance(composed, sql.Literal):
        # Use public .wrapped attribute
        val = composed.wrapped
        if isinstance(val, str):
            return repr(val)  # Returns 'value' with quotes
        return str(val)
    elif isinstance(composed, sql.Identifier):
        # Use public .strings attribute (tuple of identifier parts)
        parts = composed.strings
        return '"' + ".".join(parts) + '"'
    else:
        return str(composed)


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
        """Should raise DatabaseConnectionError when executing without connection."""
        client = AgeGraphClient(mock_db_settings)

        with pytest.raises(DatabaseConnectionError):
            client.execute_cypher("MATCH (n) RETURN n")


class TestCypherSqlWrapping:
    """Tests for Cypher query SQL wrapping logic."""

    def test_build_cypher_sql_wraps_query(self, mock_db_settings):
        """Should wrap Cypher query in AGE SQL format."""
        client = AgeGraphClient(mock_db_settings)

        sql_obj = client._build_cypher_sql("MATCH (n) RETURN n")
        # Convert sql.Composable to string for assertions
        sql_str = composable_to_string(sql_obj)

        assert "cypher(" in sql_str
        assert "MATCH (n) RETURN n" in sql_str
        assert "agtype" in sql_str

    def test_build_cypher_sql_includes_graph_name_placeholder(self, mock_db_settings):
        """SQL should include placeholder for graph name parameter."""
        client = AgeGraphClient(mock_db_settings)

        sql_obj = client._build_cypher_sql("CREATE (n:Node)")
        # Convert sql.Composable to string for assertions
        sql_str = composable_to_string(sql_obj)

        # The graph name should be embedded in the SQL (as a literal)
        assert client.graph_name in sql_str


class TestNonceGeneration:
    """Tests for nonce generation."""

    def test_generate_nonce_returns_64_characters(self, mock_db_settings):
        """Nonce should be exactly 64 characters long."""
        nonce = generate_cypher_nonce()

        assert len(nonce) == 64

    def test_generate_nonce_contains_only_letters(self, mock_db_settings):
        """Nonce should contain only ASCII letters."""
        nonce = generate_cypher_nonce()

        assert nonce.isalpha()

    def test_generate_nonce_is_unique(self, mock_db_settings):
        """Each call should generate a different nonce."""
        nonces = [generate_cypher_nonce() for _ in range(100)]

        # All nonces should be unique
        assert len(set(nonces)) == 100


class TestSecureCypherSql:
    """Tests for secure Cypher SQL building with unique tags."""

    def test_build_secure_cypher_sql_wraps_query(self, mock_db_settings):
        """Should wrap Cypher query in AGE SQL format."""
        client = AgeGraphClient(mock_db_settings)
        sql_obj = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
        )
        # Convert sql.Composable to string for assertions
        sql_str = composable_to_string(sql_obj)

        assert "cypher(" in sql_str
        assert "MATCH (n) RETURN n" in sql_str
        assert "agtype" in sql_str
        assert "test_graph" in sql_str

    def test_build_secure_cypher_sql_uses_unique_tag(self, mock_db_settings):
        """Should use a unique tag instead of $$."""
        client = AgeGraphClient(mock_db_settings)
        sql_obj = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
        )
        # Convert sql.Composable to string for assertions
        sql_str = composable_to_string(sql_obj)

        # Should not use bare $$ tags
        assert "$$" not in sql_str
        # Should have $ characters for the tag
        assert "$" in sql_str

    def test_build_secure_cypher_sql_with_custom_nonce_generator(
        self, mock_db_settings
    ):
        """Should use custom nonce generator when provided."""
        client = AgeGraphClient(mock_db_settings)
        custom_nonce = "customnonce123"

        sql_obj = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
            nonce_generator=lambda: custom_nonce,
        )
        # Convert sql.Composable to string for assertions
        sql_str = composable_to_string(sql_obj)

        assert f"${custom_nonce}$" in sql_str

    def test_build_secure_cypher_sql_raises_on_nonce_in_query(self, mock_db_settings):
        """Should raise InsecureCypherQueryError if nonce appears in query."""
        client = AgeGraphClient(mock_db_settings)
        malicious_nonce = "injected"
        malicious_query = f"MATCH (n) WHERE n.name = '{malicious_nonce}' RETURN n"

        with pytest.raises(InsecureCypherQueryError) as exc_info:
            client.build_secure_cypher_sql(
                graph_name="test_graph",
                query=malicious_query,
                nonce_generator=lambda: malicious_nonce,
            )

        assert "nonce detected" in str(exc_info.value).lower()
        assert exc_info.value.query == malicious_query

    def test_build_secure_cypher_sql_different_queries_get_different_tags(
        self, mock_db_settings
    ):
        """Each query should get a unique tag."""
        import re

        client = AgeGraphClient(mock_db_settings)
        sql_obj1 = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
        )
        sql_obj2 = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
        )
        # Convert sql.Composable to string for assertions
        sql_str1 = composable_to_string(sql_obj1)
        sql_str2 = composable_to_string(sql_obj2)

        # Extract the tag from each SQL (between first $ and next $)
        tags1 = re.findall(r"\$([a-zA-Z]+)\$", sql_str1)
        tags2 = re.findall(r"\$([a-zA-Z]+)\$", sql_str2)

        assert len(tags1) >= 1
        assert len(tags2) >= 1
        # Tags should be different for each call
        assert tags1[0] != tags2[0]

    def test_build_secure_cypher_sql_handles_special_characters_in_query(
        self, mock_db_settings
    ):
        """Should handle queries with special characters."""
        client = AgeGraphClient(mock_db_settings)
        query_with_special = "MATCH (n) WHERE n.name = 'O\\'Brien' RETURN n"

        sql_obj = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query=query_with_special,
        )
        # Convert sql.Composable to string for assertions
        sql_str = composable_to_string(sql_obj)

        assert query_with_special in sql_str
