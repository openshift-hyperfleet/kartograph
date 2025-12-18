"""Unit tests for Graph HTTP routes."""

from unittest.mock import Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from graph.domain.value_objects import (
    EdgeRecord,
    MutationResult,
    NodeRecord,
)


@pytest.fixture
def mock_query_service():
    """Mock GraphQueryService for testing."""
    return Mock()


@pytest.fixture
def mock_mutation_service():
    """Mock GraphMutationService for testing."""
    return Mock()


@pytest.fixture
def test_client(mock_query_service, mock_mutation_service):
    """Create TestClient with mocked dependencies."""
    from fastapi import FastAPI

    from graph import dependencies
    from graph.presentation import routes

    app = FastAPI()

    # Override dependencies with mocks
    app.dependency_overrides[dependencies.get_graph_query_service] = (
        lambda: mock_query_service
    )
    app.dependency_overrides[dependencies.get_graph_mutation_service] = (
        lambda: mock_mutation_service
    )

    app.include_router(routes.router)

    return TestClient(app)


class TestApplyMutationsRoute:
    """Tests for POST /graph/mutations endpoint."""

    def test_apply_mutations_success(self, test_client, mock_mutation_service):
        """Should apply mutations from JSONL and return success result."""
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=True,
            operations_applied=2,
        )

        jsonl_data = '{"op": "CREATE", "type": "node", "id": "person:abc123def456789a", "label": "person", "set_properties": {"slug": "alice", "name": "Alice", "data_source_id": "ds-123", "source_path": "people/alice.md"}}\n{"op": "UPDATE", "type": "node", "id": "person:abc123def456789a", "set_properties": {"email": "alice@example.com"}}'

        response = test_client.post(
            "/graph/mutations",
            content=jsonl_data,
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["operations_applied"] == 2

        # Verify service was called with JSONL string
        mock_mutation_service.apply_mutations_from_jsonl.assert_called_once_with(
            jsonl_content=jsonl_data
        )

    def test_apply_mutations_failure_returns_500(
        self, test_client, mock_mutation_service
    ):
        """Should return 500 when mutation application fails."""
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=False,
            operations_applied=0,
            errors=["Database connection failed"],
        )

        jsonl_data = '{"op": "DELETE", "type": "node", "id": "person:abc123def456789a"}'

        response = test_client.post(
            "/graph/mutations",
            content=jsonl_data,
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "errors" in response.json()["detail"]

    def test_apply_whitespace_only_jsonl(self, test_client, mock_mutation_service):
        """Should handle JSONL with only whitespace/newlines."""
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=True,
            operations_applied=0,
        )

        response = test_client.post(
            "/graph/mutations",
            content="\n\n  \n",  # Whitespace only
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["operations_applied"] == 0

    def test_apply_mutations_validation_error_returns_422(
        self, test_client, mock_mutation_service
    ):
        """Should return 422 for validation errors."""
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=False,
            operations_applied=0,
            errors=["JSON parse error: Invalid syntax"],
        )

        invalid_jsonl = "not valid json"

        response = test_client.post(
            "/graph/mutations",
            content=invalid_jsonl,
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "errors" in response.json()["detail"]


class TestFindBySlugRoute:
    """Tests for GET /graph/nodes/by-slug endpoint."""

    def test_find_by_slug_success(self, test_client, mock_query_service):
        """Should find nodes by slug."""
        mock_nodes = [
            NodeRecord(
                id="person:abc123def456789a",
                label="person",
                properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]

        mock_query_service.search_by_slug.return_value = mock_nodes

        response = test_client.get("/graph/nodes/by-slug?slug=alice")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["properties"]["slug"] == "alice"

    def test_find_by_slug_with_type_filter(self, test_client, mock_query_service):
        """Should filter by node type when provided."""
        mock_nodes = [
            NodeRecord(
                id="person:abc123def456789a",
                label="person",
                properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]

        mock_query_service.search_by_slug.return_value = mock_nodes

        response = test_client.get("/graph/nodes/by-slug?slug=alice&node_type=Person")

        assert response.status_code == status.HTTP_200_OK
        mock_query_service.search_by_slug.assert_called_once_with(
            "alice", node_type="Person"
        )


class TestGetNeighborsRoute:
    """Tests for GET /graph/nodes/{node_id}/neighbors endpoint."""

    def test_get_neighbors_success(self, test_client, mock_query_service):
        """Should get neighbors and edges."""
        from graph.ports.protocols import NodeNeighborsResult

        mock_central_node = NodeRecord(
            id="person:abc123def456789a",
            label="person",
            properties={
                "slug": "alice",
                "name": "Alice",
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )
        mock_neighbor_nodes = [
            NodeRecord(
                id="person:def456abc123789a",
                label="person",
                properties={
                    "slug": "bob",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "people/bob.md",
                },
            )
        ]
        mock_connecting_edges = [
            EdgeRecord(
                id="knows:aaa111bbb222ccc3",
                label="knows",
                start_id="person:abc123def456789a",
                end_id="person:def456abc123789a",
                properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]

        mock_query_service.get_neighbors.return_value = NodeNeighborsResult(
            central_node=mock_central_node,
            nodes=mock_neighbor_nodes,
            edges=mock_connecting_edges,
        )

        response = test_client.get("/graph/nodes/person:abc123def456789a/neighbors")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "central_node" in data
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert data["nodes"][0]["properties"]["slug"] == "bob"
        assert data["central_node"]["id"] == "person:abc123def456789a"

    def test_get_neighbors_no_results(self, test_client, mock_query_service):
        """Should return empty arrays for isolated node."""
        from graph.ports.protocols import NodeNeighborsResult

        mock_central_node = NodeRecord(
            id="person:isolated111111",
            label="person",
            properties={
                "slug": "isolated",
                "data_source_id": "ds-123",
            },
        )

        mock_query_service.get_neighbors.return_value = NodeNeighborsResult(
            central_node=mock_central_node,
            nodes=[],
            edges=[],
        )

        response = test_client.get("/graph/nodes/person:isolated111111/neighbors")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["central_node"]["id"] == "person:isolated111111"
        assert data["nodes"] == []
        assert data["edges"] == []
