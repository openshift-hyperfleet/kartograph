"""Unit tests for Graph application services."""

from unittest.mock import create_autospec

import pytest

from graph.application.services import GraphQueryService
from graph.domain.value_objects import EdgeRecord, NodeRecord
from graph.ports.repositories import IGraphReadOnlyRepository


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repo = create_autospec(IGraphReadOnlyRepository, instance=True)
    return repo


@pytest.fixture
def mock_probe():
    """Create a mock probe."""
    from graph.application.observability import GraphServiceProbe

    return create_autospec(GraphServiceProbe, instance=True)


@pytest.fixture
def service(mock_repository, mock_probe):
    """Create a service with mock dependencies."""
    return GraphQueryService(repository=mock_repository, probe=mock_probe)


class TestGraphQueryServiceInit:
    """Tests for service initialization."""

    def test_stores_repository(self, mock_repository):
        """Service should store the repository reference."""
        service = GraphQueryService(repository=mock_repository)
        assert service._repository is mock_repository

    def test_uses_default_probe_when_not_provided(self, mock_repository):
        """Service should create default probe when not provided."""
        service = GraphQueryService(repository=mock_repository)
        assert service._probe is not None


class TestSearchBySlug:
    """Tests for search_by_slug method."""

    def test_delegates_to_repository(self, service, mock_repository):
        """Service should delegate slug search to repository."""
        expected = [NodeRecord(id="n1", label="person", properties={})]
        mock_repository.find_nodes_by_slug.return_value = expected

        result = service.search_by_slug("alice-smith", node_type="Person")

        mock_repository.find_nodes_by_slug.assert_called_once_with(
            "alice-smith", node_type="Person"
        )
        assert result == expected

    def test_records_observation(self, service, mock_repository, mock_probe):
        """Service should record observation via probe."""
        mock_repository.find_nodes_by_slug.return_value = [
            NodeRecord(id="n1", label="person", properties={}),
            NodeRecord(id="n2", label="person", properties={}),
        ]

        service.search_by_slug("alice", node_type="Person")

        mock_probe.slug_searched.assert_called_once_with(
            slug="alice",
            node_type="Person",
            result_count=2,
        )

    def test_handles_none_node_type(self, service, mock_repository):
        """Service should handle None node_type."""
        mock_repository.find_nodes_by_slug.return_value = []

        service.search_by_slug("some-slug")

        mock_repository.find_nodes_by_slug.assert_called_once_with(
            "some-slug", node_type=None
        )


class TestGetNeighbors:
    """Tests for get_neighbors method."""

    def test_delegates_to_repository(self, service, mock_repository):
        """Service should delegate to repository."""
        from graph.ports.protocols import NodeNeighborsResult

        expected_central = NodeRecord(id="n1", label="Node", properties={})
        expected_nodes = [NodeRecord(id="n2", label="Other", properties={})]
        expected_edges = [
            EdgeRecord(
                id="e1", label="knows", start_id="n1", end_id="n2", properties={}
            )
        ]
        expected_result = NodeNeighborsResult(
            central_node=expected_central, nodes=expected_nodes, edges=expected_edges
        )
        mock_repository.get_neighbors.return_value = expected_result

        result = service.get_neighbors("n1")

        mock_repository.get_neighbors.assert_called_once_with("n1")
        assert result == expected_result


class TestGenerateEntityId:
    """Tests for generate_entity_id method."""

    def test_delegates_to_repository(self, service, mock_repository):
        """Service should delegate to repository."""
        mock_repository.generate_id.return_value = "person:abc123"

        result = service.generate_entity_id("person", "alice-smith")

        mock_repository.generate_id.assert_called_once_with("person", "alice-smith")
        assert result == "person:abc123"


class TestExecuteExplorationQuery:
    """Tests for execute_exploration_query method."""

    def test_delegates_to_repository(self, service, mock_repository):
        """Service should delegate to repository."""
        mock_repository.execute_raw_query.return_value = [{"name": "Test"}]

        result = service.execute_exploration_query("MATCH (n) RETURN n.name")

        mock_repository.execute_raw_query.assert_called_once_with(
            "MATCH (n) RETURN n.name"
        )
        assert result == [{"name": "Test"}]

    def test_records_observation(self, service, mock_repository, mock_probe):
        """Service should record observation via probe."""
        mock_repository.execute_raw_query.return_value = [{"a": 1}, {"a": 2}]

        service.execute_exploration_query("MATCH (n) RETURN n")

        mock_probe.raw_query_executed.assert_called_once_with(
            query="MATCH (n) RETURN n",
            result_count=2,
        )
