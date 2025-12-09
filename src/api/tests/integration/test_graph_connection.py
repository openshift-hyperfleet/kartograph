"""Integration tests for database connection layer.

These tests verify actual database connectivity and Cypher query execution
against a real PostgreSQL/AGE instance.

Run with: pytest -m integration tests/integration/
Requires: Running PostgreSQL with AGE extension (docker compose up -d postgres)
"""

import pytest

from graph.infrastructure.age_client import AgeGraphClient


pytestmark = pytest.mark.integration


class TestDatabaseConnection:
    """Tests for database connection lifecycle."""

    def test_connect_establishes_connection(self, graph_client: AgeGraphClient):
        """Client should establish connection successfully."""
        assert graph_client.is_connected() is True

    def test_verify_connection_returns_true_when_healthy(
        self, graph_client: AgeGraphClient
    ):
        """Connection verification should succeed on healthy connection."""
        assert graph_client.verify_connection() is True

    def test_disconnect_closes_connection(self, integration_db_settings):
        """Disconnecting should close the connection."""
        client = AgeGraphClient(integration_db_settings)
        client.connect()
        assert client.is_connected() is True

        client.disconnect()
        assert client.is_connected() is False

    def test_graph_name_is_accessible(self, graph_client: AgeGraphClient):
        """Graph name should be accessible from client."""
        assert graph_client.graph_name == "test_graph"


class TestCypherQueryExecution:
    """Tests for Cypher query execution."""

    def test_execute_simple_match_query(self, clean_graph: AgeGraphClient):
        """Should execute a simple MATCH query."""
        result = clean_graph.execute_cypher("MATCH (n) RETURN n LIMIT 1")

        assert result is not None
        assert result.row_count >= 0

    def test_execute_create_query(self, clean_graph: AgeGraphClient):
        """Should execute a CREATE query."""
        result = clean_graph.execute_cypher(
            "CREATE (n:TestNode {name: 'test'}) RETURN n"
        )

        assert result.row_count == 1

    def test_execute_match_after_create(self, clean_graph: AgeGraphClient):
        """Should be able to match created nodes."""
        clean_graph.execute_cypher("CREATE (n:TestNode {name: 'findme'})")

        result = clean_graph.execute_cypher(
            "MATCH (n:TestNode {name: 'findme'}) RETURN n"
        )

        assert result.row_count == 1


class TestTransactions:
    """Tests for transaction management."""

    def test_transaction_commits_on_success(self, clean_graph: AgeGraphClient):
        """Transaction should commit when no exception occurs."""
        with clean_graph.transaction() as tx:
            tx.execute_cypher("CREATE (n:TxTest {name: 'committed'})")

        # Verify committed
        result = clean_graph.execute_cypher(
            "MATCH (n:TxTest {name: 'committed'}) RETURN n"
        )
        assert result.row_count == 1

    def test_transaction_rolls_back_on_exception(self, clean_graph: AgeGraphClient):
        """Transaction should rollback when exception occurs."""
        try:
            with clean_graph.transaction() as tx:
                tx.execute_cypher("CREATE (n:TxTest {name: 'rolledback'})")
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Verify rolled back
        result = clean_graph.execute_cypher(
            "MATCH (n:TxTest {name: 'rolledback'}) RETURN n"
        )
        assert result.row_count == 0
