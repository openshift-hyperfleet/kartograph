"""Unit tests for AgeGraphClient.

These tests use mocks to test the client logic without requiring a database.
"""

import pytest

from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.exceptions import InsecureCypherQueryError
from infrastructure.database.exceptions import DatabaseConnectionError


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


class TestNonceGeneration:
    """Tests for nonce generation."""

    def test_generate_nonce_returns_64_characters(self, mock_db_settings):
        """Nonce should be exactly 64 characters long."""
        client = AgeGraphClient(mock_db_settings)
        nonce = client._generate_nonce()

        assert len(nonce) == 64

    def test_generate_nonce_contains_only_letters(self, mock_db_settings):
        """Nonce should contain only ASCII letters."""
        client = AgeGraphClient(mock_db_settings)
        nonce = client._generate_nonce()

        assert nonce.isalpha()

    def test_generate_nonce_is_unique(self, mock_db_settings):
        """Each call should generate a different nonce."""
        client = AgeGraphClient(mock_db_settings)
        nonces = [client._generate_nonce() for _ in range(100)]

        # All nonces should be unique
        assert len(set(nonces)) == 100


class TestSecureCypherSql:
    """Tests for secure Cypher SQL building with unique tags."""

    def test_build_secure_cypher_sql_wraps_query(self, mock_db_settings):
        """Should wrap Cypher query in AGE SQL format."""
        client = AgeGraphClient(mock_db_settings)
        sql = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
        )

        assert "cypher(" in sql
        assert "MATCH (n) RETURN n" in sql
        assert "agtype" in sql
        assert "test_graph" in sql

    def test_build_secure_cypher_sql_uses_unique_tag(self, mock_db_settings):
        """Should use a unique tag instead of $$."""
        client = AgeGraphClient(mock_db_settings)
        sql = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
        )

        # Should not use bare $$ tags
        assert "$$" not in sql
        # Should have $ characters for the tag
        assert "$" in sql

    def test_build_secure_cypher_sql_with_custom_nonce_generator(
        self, mock_db_settings
    ):
        """Should use custom nonce generator when provided."""
        client = AgeGraphClient(mock_db_settings)
        custom_nonce = "customnonce123"

        sql = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
            nonce_generator=lambda: custom_nonce,
        )

        assert f"${custom_nonce}$" in sql

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
        client = AgeGraphClient(mock_db_settings)
        sql1 = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
        )
        sql2 = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query="MATCH (n) RETURN n",
        )

        # Extract the tag from each SQL (between first $ and next $)
        import re

        tags1 = re.findall(r"\$([a-zA-Z]+)\$", sql1)
        tags2 = re.findall(r"\$([a-zA-Z]+)\$", sql2)

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

        sql = client.build_secure_cypher_sql(
            graph_name="test_graph",
            query=query_with_special,
        )

        assert query_with_special in sql
