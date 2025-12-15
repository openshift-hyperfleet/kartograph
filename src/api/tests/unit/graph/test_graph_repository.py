"""Unit tests for GraphExtractionReadOnlyRepository implementation."""

from unittest.mock import MagicMock, create_autospec

import pytest

from graph.infrastructure.graph_repository import GraphExtractionReadOnlyRepository
from graph.ports.protocols import CypherResult, GraphClientProtocol
from graph.ports.repositories import IGraphReadOnlyRepository


@pytest.fixture
def mock_graph_client():
    """Create a mock graph client."""
    client = create_autospec(GraphClientProtocol, instance=True)
    client.graph_name = "test_graph"

    # Mock the transaction context manager
    # Store mock_tx as an attribute so tests can access it
    mock_tx = MagicMock()
    mock_tx.execute_cypher.return_value = CypherResult(rows=tuple(), row_count=0)
    mock_tx.execute_sql.return_value = None  # execute_sql returns None
    client.transaction.return_value.__enter__.return_value = mock_tx
    client.transaction.return_value.__exit__.return_value = None

    # Store reference for tests
    client._mock_tx = mock_tx

    return client


@pytest.fixture
def repository(mock_graph_client):
    """Create a repository with mock client."""
    return GraphExtractionReadOnlyRepository(
        client=mock_graph_client,
        data_source_id="ds-123",
    )


class TestGraphExtractionReadOnlyRepositoryProtocolCompliance:
    """Tests that GraphExtractionReadOnlyRepository satisfies IGraphReadOnlyRepository."""

    def test_implements_protocol(self, repository):
        """Repository should implement IGraphReadOnlyRepository protocol."""
        assert isinstance(repository, IGraphReadOnlyRepository)


class TestGraphExtractionReadOnlyRepositoryInit:
    """Tests for repository initialization."""

    def test_stores_data_source_id(self, mock_graph_client):
        """Repository should store the data_source_id for scoping."""
        repo = GraphExtractionReadOnlyRepository(
            client=mock_graph_client,
            data_source_id="ds-456",
        )
        assert repo._data_source_id == "ds-456"

    def test_stores_client_reference(self, mock_graph_client):
        """Repository should store the client reference."""
        repo = GraphExtractionReadOnlyRepository(
            client=mock_graph_client,
            data_source_id="ds-123",
        )
        assert repo._client is mock_graph_client


class TestGenerateId:
    """Tests for deterministic ID generation."""

    def test_is_deterministic(self, repository):
        """Same inputs should produce same ID."""
        id1 = repository.generate_id("person", "alice-smith")
        id2 = repository.generate_id("person", "alice-smith")
        assert id1 == id2

    def test_includes_type_prefix(self, repository):
        """Generated ID should include entity type as prefix."""
        id_value = repository.generate_id("person", "alice-smith")
        assert id_value.startswith("person:")

    def test_different_for_different_slugs(self, repository):
        """Different slugs should produce different IDs."""
        id1 = repository.generate_id("person", "alice-smith")
        id2 = repository.generate_id("person", "bob-jones")
        assert id1 != id2

    def test_different_for_different_types(self, repository):
        """Different types should produce different IDs."""
        id1 = repository.generate_id("person", "alice")
        id2 = repository.generate_id("repository", "alice")
        assert id1 != id2

    def test_doesnt_incorporates_data_source(self, mock_graph_client):
        """IDs from different data sources should differ.

        TODO: Once Tenant IDs are part of the system, ensure that
        cross-tenant IDs differ.
        """
        repo1 = GraphExtractionReadOnlyRepository(
            client=mock_graph_client, data_source_id="ds-1"
        )
        repo2 = GraphExtractionReadOnlyRepository(
            client=mock_graph_client, data_source_id="ds-2"
        )

        id1 = repo1.generate_id("person", "alice")
        id2 = repo2.generate_id("person", "alice")
        assert id1 == id2

    def test_hash_portion_is_hex(self, repository):
        """Hash portion of ID should be valid hex."""
        id_value = repository.generate_id("person", "alice")
        hash_part = id_value.split(":")[1]
        # Should be valid hex characters
        assert all(c in "0123456789abcdef" for c in hash_part)


class TestFindNodesByPath:
    """Tests for find_nodes_by_path method."""

    def test_returns_empty_when_no_results(self, repository, mock_graph_client):
        """Should return empty lists when no nodes found."""
        mock_graph_client.execute_cypher.return_value = CypherResult(
            rows=tuple(),
            row_count=0,
        )

        nodes, edges = repository.find_nodes_by_path("nonexistent/path.md")

        assert nodes == []
        assert edges == []

    def test_executes_query_with_path(self, repository, mock_graph_client):
        """Query should include the path parameter."""
        mock_graph_client.execute_cypher.return_value = CypherResult(
            rows=tuple(),
            row_count=0,
        )

        repository.find_nodes_by_path("some/path.md")

        call_args = mock_graph_client.execute_cypher.call_args
        query = call_args[0][0]
        assert "some/path.md" in query

    def test_scopes_to_data_source(self, repository, mock_graph_client):
        """Query should be scoped to the repository's data_source_id."""
        mock_graph_client.execute_cypher.return_value = CypherResult(
            rows=tuple(),
            row_count=0,
        )

        repository.find_nodes_by_path("some/path.md")

        call_args = mock_graph_client.execute_cypher.call_args
        query = call_args[0][0]
        assert "ds-123" in query


class TestFindNodesBySlug:
    """Tests for find_nodes_by_slug method."""

    def test_returns_empty_when_no_results(self, repository, mock_graph_client):
        """Should return empty list when no nodes found."""
        mock_graph_client.execute_cypher.return_value = CypherResult(
            rows=tuple(),
            row_count=0,
        )

        nodes = repository.find_nodes_by_slug("nonexistent-slug")

        assert nodes == []

    def test_executes_query_with_slug(self, repository, mock_graph_client):
        """Query should include the slug parameter."""
        mock_graph_client.execute_cypher.return_value = CypherResult(
            rows=tuple(),
            row_count=0,
        )

        repository.find_nodes_by_slug("alice-smith")

        call_args = mock_graph_client.execute_cypher.call_args
        query = call_args[0][0]
        assert "alice-smith" in query

    def test_includes_type_filter_when_provided(self, repository, mock_graph_client):
        """Query should include type filter when node_type is provided."""
        mock_graph_client.execute_cypher.return_value = CypherResult(
            rows=tuple(),
            row_count=0,
        )

        repository.find_nodes_by_slug("alice-smith", node_type="Person")

        call_args = mock_graph_client.execute_cypher.call_args
        query = call_args[0][0]
        assert "Person" in query


class TestGetNeighbors:
    """Tests for get_neighbors method."""

    def test_returns_empty_when_no_neighbors(self, repository, mock_graph_client):
        """Should return empty lists when no neighbors found."""
        from age.models import Vertex

        # Mock a central node with no neighbors (OPTIONAL MATCH returns null for neighbor/relationship)
        central_vertex = Vertex(
            id=1,
            label="Node",
            properties={"id": "node:abc123", "data_source_id": "test-ds"},
        )

        mock_graph_client.execute_cypher.return_value = CypherResult(
            rows=(
                (
                    {
                        "central_node": central_vertex,
                        "neighbor": None,
                        "relationship": None,
                    },
                ),
            ),
            row_count=1,
        )

        result = repository.get_neighbors("node:abc123")

        assert result.nodes == []
        assert result.edges == []
        assert result.central_node.properties["id"] == "node:abc123"


class TestExecuteRawQuery:
    """Tests for execute_raw_query method."""

    def test_rejects_create_statements(self, repository, mock_graph_client):
        """Should reject queries containing CREATE."""
        from infrastructure.database.exceptions import GraphQueryError

        with pytest.raises(GraphQueryError) as exc_info:
            repository.execute_raw_query("CREATE (n:Node)")

        assert "CREATE" in str(exc_info.value)

    def test_rejects_delete_statements(self, repository, mock_graph_client):
        """Should reject queries containing DELETE."""
        from infrastructure.database.exceptions import GraphQueryError

        with pytest.raises(GraphQueryError) as exc_info:
            repository.execute_raw_query("MATCH (n) DELETE n")

        assert "DELETE" in str(exc_info.value)

    def test_rejects_set_statements(self, repository, mock_graph_client):
        """Should reject queries containing SET."""
        from infrastructure.database.exceptions import GraphQueryError

        with pytest.raises(GraphQueryError) as exc_info:
            repository.execute_raw_query("MATCH (n) SET n.name = 'test'")

        assert "SET" in str(exc_info.value)

    def test_adds_limit_when_missing(self, repository, mock_graph_client):
        """Should add LIMIT 100 when not present in query."""
        mock_tx = mock_graph_client._mock_tx
        mock_tx.execute_cypher.return_value = CypherResult(
            rows=tuple(),
            row_count=0,
        )

        repository.execute_raw_query("MATCH (n) RETURN n")

        # Check that execute_sql was called for SET LOCAL statement_timeout
        mock_tx.execute_sql.assert_called_once()
        sql_call_args = mock_tx.execute_sql.call_args[0][0]
        assert "SET LOCAL statement_timeout" in sql_call_args

        # Check the transaction's execute_cypher was called with LIMIT
        call_args = mock_tx.execute_cypher.call_args_list
        assert len(call_args) >= 1
        query = call_args[0][0][0]
        assert "LIMIT 100" in query

    def test_preserves_existing_limit(self, repository, mock_graph_client):
        """Should preserve existing LIMIT in query."""
        mock_tx = mock_graph_client._mock_tx
        mock_tx.execute_cypher.return_value = CypherResult(
            rows=tuple(),
            row_count=0,
        )

        repository.execute_raw_query("MATCH (n) RETURN n LIMIT 50")

        # Check the transaction's execute_cypher was called
        call_args = mock_tx.execute_cypher.call_args_list
        assert len(call_args) >= 1
        query = call_args[0][0][0]
        # Should not have duplicate LIMIT
        assert query.count("LIMIT") == 1

    def test_returns_list_of_dicts(self, repository, mock_graph_client):
        """Should return results as list of dictionaries."""
        mock_tx = mock_graph_client._mock_tx
        # execute_cypher returns the actual data (execute_sql is separate)
        mock_tx.execute_cypher.return_value = CypherResult(
            rows=(("value1",), ("value2",)), row_count=2
        )

        results = repository.execute_raw_query("MATCH (n) RETURN n.name")

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)
