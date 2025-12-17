"""Unit tests for QueryGraphRepository."""

from unittest.mock import MagicMock, create_autospec

import pytest
from age.models import Edge as AgeEdge
from age.models import Vertex as AgeVertex

from graph.ports.protocols import (
    CypherResult,
    GraphClientProtocol,
    GraphTransactionProtocol,
)
from query.domain.value_objects import QueryExecutionError, QueryForbiddenError
from query.infrastructure.query_repository import QueryGraphRepository


@pytest.fixture
def mock_client():
    """Create mock graph client."""
    client = create_autospec(GraphClientProtocol, instance=True)
    client.graph_name = "test_graph"
    return client


@pytest.fixture
def mock_transaction():
    """Create mock transaction."""
    return create_autospec(GraphTransactionProtocol, instance=True)


@pytest.fixture
def repository(mock_client):
    """Create repository with mock client."""
    return QueryGraphRepository(client=mock_client)


class TestInit:
    """Tests for repository initialization."""

    def test_stores_client(self, mock_client):
        """Should store client reference."""
        repo = QueryGraphRepository(client=mock_client)
        assert repo._client is mock_client


class TestValidateReadOnly:
    """Tests for read-only validation."""

    def test_rejects_create(self, repository):
        """Should reject CREATE queries."""
        with pytest.raises(QueryForbiddenError) as exc_info:
            repository._validate_read_only("CREATE (n:Test)")

        assert "CREATE" in str(exc_info.value)
        assert "read-only" in str(exc_info.value).lower()

    def test_rejects_delete(self, repository):
        """Should reject DELETE queries."""
        with pytest.raises(QueryForbiddenError):
            repository._validate_read_only("MATCH (n) DELETE n")

    def test_rejects_set(self, repository):
        """Should reject SET queries."""
        with pytest.raises(QueryForbiddenError):
            repository._validate_read_only("MATCH (n) SET n.x = 1")

    def test_rejects_remove(self, repository):
        """Should reject REMOVE queries."""
        with pytest.raises(QueryForbiddenError):
            repository._validate_read_only("MATCH (n) REMOVE n.x")

    def test_rejects_merge(self, repository):
        """Should reject MERGE queries."""
        with pytest.raises(QueryForbiddenError):
            repository._validate_read_only("MERGE (n:Test)")

    def test_allows_match_return(self, repository):
        """Should allow pure MATCH-RETURN queries."""
        # Should not raise
        repository._validate_read_only("MATCH (n) RETURN n")

    def test_case_insensitive(self, repository):
        """Should detect mutation keywords case-insensitively."""
        with pytest.raises(QueryForbiddenError):
            repository._validate_read_only("create (n:Test)")

    def test_allows_where_clause(self, repository):
        """Should allow WHERE clauses."""
        repository._validate_read_only("MATCH (n) WHERE n.id = 123 RETURN n")

    def test_allows_order_by(self, repository):
        """Should allow ORDER BY clauses."""
        repository._validate_read_only("MATCH (n) RETURN n ORDER BY n.name")

    def test_allows_limit(self, repository):
        """Should allow LIMIT clauses."""
        repository._validate_read_only("MATCH (n) RETURN n LIMIT 10")

    def test_stores_query_in_exception(self, repository):
        """Should store query in exception for debugging."""
        query = "CREATE (n:Test)"
        with pytest.raises(QueryForbiddenError) as exc_info:
            repository._validate_read_only(query)

        assert exc_info.value.query == query


class TestEnsureLimit:
    """Tests for LIMIT enforcement."""

    def test_adds_limit_when_missing(self, repository):
        """Should add LIMIT when not present."""
        query = repository._ensure_limit("MATCH (n) RETURN n", 100)

        assert "LIMIT 100" in query

    def test_preserves_existing_limit(self, repository):
        """Should preserve explicit LIMIT."""
        original = "MATCH (n) RETURN n LIMIT 50"
        query = repository._ensure_limit(original, 100)

        assert query == original

    def test_case_insensitive_limit_detection(self, repository):
        """Should detect LIMIT case-insensitively."""
        original = "MATCH (n) RETURN n limit 50"
        query = repository._ensure_limit(original, 100)

        assert query == original

    def test_preserves_multiline_query(self, repository):
        """Should handle multiline queries correctly."""
        original = """MATCH (n)
WHERE n.active = true
RETURN n"""
        query = repository._ensure_limit(original, 100)

        assert "LIMIT 100" in query
        assert "MATCH (n)" in query


class TestExecuteCypher:
    """Tests for execute_cypher method."""

    def test_validates_read_only_before_execution(self, repository, mock_client):
        """Should validate read-only before executing query."""
        with pytest.raises(QueryForbiddenError) as exc_info:
            repository.execute_cypher("CREATE (n:Test)")

        # Should fail before calling client
        mock_client.transaction.assert_not_called()
        assert "read-only" in str(exc_info.value).lower()

    def test_ensures_limit_before_execution(
        self, repository, mock_client, mock_transaction
    ):
        """Should add LIMIT before executing query."""
        mock_client.transaction.return_value.__enter__ = MagicMock(
            return_value=mock_transaction
        )
        mock_client.transaction.return_value.__exit__ = MagicMock(return_value=False)
        mock_transaction.execute_cypher.return_value = CypherResult(
            rows=(), row_count=0
        )

        repository.execute_cypher("MATCH (n) RETURN n", max_rows=50)

        # Verify the query passed to execute_cypher includes LIMIT
        call_args = mock_transaction.execute_cypher.call_args
        query_executed = call_args[0][0]
        assert "LIMIT 50" in query_executed

    def test_sets_statement_timeout(self, repository, mock_client, mock_transaction):
        """Should set PostgreSQL statement_timeout."""
        mock_client.transaction.return_value.__enter__ = MagicMock(
            return_value=mock_transaction
        )
        mock_client.transaction.return_value.__exit__ = MagicMock(return_value=False)
        mock_transaction.execute_cypher.return_value = CypherResult(
            rows=(), row_count=0
        )

        repository.execute_cypher("MATCH (n) RETURN n", timeout_seconds=5)

        mock_transaction.execute_sql.assert_called_once()
        sql_call = mock_transaction.execute_sql.call_args[0][0]
        assert "statement_timeout" in sql_call
        assert "5000" in sql_call  # 5 seconds = 5000ms

    def test_uses_transaction_context(self, repository, mock_client, mock_transaction):
        """Should execute query within transaction context."""
        mock_client.transaction.return_value.__enter__ = MagicMock(
            return_value=mock_transaction
        )
        mock_client.transaction.return_value.__exit__ = MagicMock(return_value=False)
        mock_transaction.execute_cypher.return_value = CypherResult(
            rows=(), row_count=0
        )

        repository.execute_cypher("MATCH (n) RETURN n")

        mock_client.transaction.assert_called_once()
        mock_transaction.execute_cypher.assert_called_once()

    def test_raises_on_execution_error(self, repository, mock_client, mock_transaction):
        """Should wrap exceptions in QueryExecutionError."""
        mock_client.transaction.return_value.__enter__ = MagicMock(
            return_value=mock_transaction
        )
        mock_client.transaction.return_value.__exit__ = MagicMock(return_value=False)
        mock_transaction.execute_cypher.side_effect = Exception("DB error")

        with pytest.raises(QueryExecutionError) as exc_info:
            repository.execute_cypher("MATCH (n) RETURN n")

        assert "DB error" in str(exc_info.value)

    def test_returns_empty_list_on_no_results(
        self, repository, mock_client, mock_transaction
    ):
        """Should return empty list when query has no results."""
        mock_client.transaction.return_value.__enter__ = MagicMock(
            return_value=mock_transaction
        )
        mock_client.transaction.return_value.__exit__ = MagicMock(return_value=False)
        mock_transaction.execute_cypher.return_value = CypherResult(
            rows=(), row_count=0
        )

        result = repository.execute_cypher("MATCH (n) RETURN n")

        assert result == []


class TestRowToDict:
    """Tests for _row_to_dict conversion."""

    def test_converts_single_vertex(self, repository):
        """Should convert single Vertex to dict."""
        vertex = AgeVertex(id=1, label="Person", properties={"name": "Alice"})
        row = (vertex,)

        result = repository._row_to_dict(row)

        assert "node" in result
        assert result["node"]["id"] == "1"
        assert result["node"]["label"] == "Person"
        assert result["node"]["properties"] == {"name": "Alice"}

    def test_converts_single_edge(self, repository):
        """Should convert single Edge to dict."""
        edge = AgeEdge(id=1, label="KNOWS", properties={"since": 2020})
        edge.start_id = 2
        edge.end_id = 3
        row = (edge,)

        result = repository._row_to_dict(row)

        assert "edge" in result
        assert result["edge"]["id"] == "1"
        assert result["edge"]["label"] == "KNOWS"
        assert result["edge"]["start_id"] == "2"
        assert result["edge"]["end_id"] == "3"
        assert result["edge"]["properties"] == {"since": 2020}

    def test_converts_scalar_value(self, repository):
        """Should convert scalar values to {value: ...}."""
        row = (42,)

        result = repository._row_to_dict(row)

        assert result == {"value": 42}

    def test_converts_map_with_vertices(self, repository):
        """Should convert maps containing vertices."""
        vertex_a = AgeVertex(id=1, label="Person", properties={"name": "Alice"})
        vertex_b = AgeVertex(id=2, label="Person", properties={"name": "Bob"})
        row = ({"person_a": vertex_a, "person_b": vertex_b},)

        result = repository._row_to_dict(row)

        assert "person_a" in result
        assert "person_b" in result
        assert result["person_a"]["label"] == "Person"
        assert result["person_a"]["properties"]["name"] == "Alice"


class TestVertexToDict:
    """Tests for _vertex_to_dict conversion."""

    def test_converts_vertex_properties(self, repository):
        """Should convert vertex with all properties."""
        vertex = AgeVertex(
            id=123, label="Person", properties={"name": "Alice", "age": 30}
        )

        result = repository._vertex_to_dict(vertex)

        assert result["id"] == "123"
        assert result["label"] == "Person"
        assert result["properties"] == {"name": "Alice", "age": 30}

    def test_handles_empty_properties(self, repository):
        """Should handle vertices with no properties."""
        vertex = AgeVertex(id=123, label="Person", properties=None)

        result = repository._vertex_to_dict(vertex)

        assert result["properties"] == {}


class TestEdgeToDict:
    """Tests for _edge_to_dict conversion."""

    def test_converts_edge_properties(self, repository):
        """Should convert edge with all properties."""
        edge = AgeEdge(
            id=456, label="KNOWS", properties={"since": 2020, "strength": 0.8}
        )
        edge.start_id = 1
        edge.end_id = 2

        result = repository._edge_to_dict(edge)

        assert result["id"] == "456"
        assert result["label"] == "KNOWS"
        assert result["start_id"] == "1"
        assert result["end_id"] == "2"
        assert result["properties"] == {"since": 2020, "strength": 0.8}

    def test_handles_empty_properties(self, repository):
        """Should handle edges with no properties."""
        edge = AgeEdge(id=456, label="KNOWS", properties=None)
        edge.start_id = 1
        edge.end_id = 2

        result = repository._edge_to_dict(edge)

        assert result["properties"] == {}
