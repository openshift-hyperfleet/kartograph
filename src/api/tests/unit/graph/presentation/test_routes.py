"""Unit tests for Graph HTTP routes."""

from unittest.mock import Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from graph.domain.value_objects import (
    EdgeRecord,
    MutationOperation,
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

    from graph.presentation import routes

    app = FastAPI()

    # Override dependencies with mocks
    app.dependency_overrides[routes.get_query_service] = lambda: mock_query_service
    app.dependency_overrides[routes.get_mutation_service] = (
        lambda: mock_mutation_service
    )

    app.include_router(routes.router)

    return TestClient(app)


class TestApplyMutationsRoute:
    """Tests for POST /graph/mutations endpoint."""

    def test_apply_mutations_success(self, test_client, mock_mutation_service):
        """Should apply mutations and return success result."""
        mock_mutation_service.apply_mutations.return_value = MutationResult(
            success=True,
            operations_applied=2,
        )

        request_data = [
            {
                "op": "CREATE",
                "type": "node",
                "id": "person:abc123def456789a",
                "label": "Person",
                "set_properties": {
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            },
            {
                "op": "UPDATE",
                "type": "node",
                "id": "person:abc123def456789a",
                "set_properties": {"email": "alice@example.com"},
            },
        ]

        response = test_client.post("/graph/mutations", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["operations_applied"] == 2

        # Verify service was called with parsed operations
        mock_mutation_service.apply_mutations.assert_called_once()
        operations = mock_mutation_service.apply_mutations.call_args[0][0]
        assert len(operations) == 2
        assert all(isinstance(op, MutationOperation) for op in operations)

    def test_apply_mutations_failure_returns_500(
        self, test_client, mock_mutation_service
    ):
        """Should return 500 when mutation application fails."""
        mock_mutation_service.apply_mutations.return_value = MutationResult(
            success=False,
            operations_applied=0,
            errors=["Database connection failed"],
        )

        request_data = [
            {
                "op": "DELETE",
                "type": "node",
                "id": "person:abc123def456789a",
            }
        ]

        response = test_client.post("/graph/mutations", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "errors" in response.json()["detail"]

    def test_apply_mutations_invalid_operation_returns_422(self, test_client):
        """Should return 422 for invalid mutation operation."""
        # Missing required 'op' field
        request_data = [
            {
                "type": "node",
                "id": "person:abc123def456789a",
            }
        ]

        response = test_client.post("/graph/mutations", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_apply_empty_mutations_list(self, test_client, mock_mutation_service):
        """Should handle empty mutations list."""
        mock_mutation_service.apply_mutations.return_value = MutationResult(
            success=True,
            operations_applied=0,
        )

        response = test_client.post("/graph/mutations", json=[])

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["operations_applied"] == 0


class TestFindByPathRoute:
    """Tests for GET /graph/nodes/by-path endpoint."""

    def test_find_by_path_success(self, test_client, mock_query_service):
        """Should find nodes and edges by path."""
        mock_nodes = [
            NodeRecord(
                id="person:abc123def456789a",
                label="Person",
                properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]
        mock_edges = [
            EdgeRecord(
                id="knows:aaa111bbb222ccc3",
                label="KNOWS",
                start_id="person:abc123def456789a",
                end_id="person:def456abc123789a",
                properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]

        mock_query_service.get_nodes_by_path.return_value = (mock_nodes, mock_edges)

        response = test_client.get("/graph/nodes/by-path?path=people/alice.md")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert data["nodes"][0]["label"] == "Person"
        assert data["edges"][0]["label"] == "KNOWS"

    def test_find_by_path_no_results(self, test_client, mock_query_service):
        """Should return empty arrays when no results found."""
        mock_query_service.get_nodes_by_path.return_value = ([], [])

        response = test_client.get("/graph/nodes/by-path?path=nonexistent.md")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["nodes"] == []
        assert data["edges"] == []


class TestFindBySlugRoute:
    """Tests for GET /graph/nodes/by-slug endpoint."""

    def test_find_by_slug_success(self, test_client, mock_query_service):
        """Should find nodes by slug."""
        mock_nodes = [
            NodeRecord(
                id="person:abc123def456789a",
                label="Person",
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
                label="Person",
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
        mock_neighbor_nodes = [
            NodeRecord(
                id="person:def456abc123789a",
                label="Person",
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
                label="KNOWS",
                start_id="person:abc123def456789a",
                end_id="person:def456abc123789a",
                properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]

        mock_query_service.get_neighbors.return_value = (
            mock_neighbor_nodes,
            mock_connecting_edges,
        )

        response = test_client.get("/graph/nodes/person:abc123def456789a/neighbors")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert data["nodes"][0]["properties"]["slug"] == "bob"

    def test_get_neighbors_no_results(self, test_client, mock_query_service):
        """Should return empty arrays for isolated node."""
        mock_query_service.get_neighbors.return_value = ([], [])

        response = test_client.get("/graph/nodes/person:isolated111111/neighbors")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["nodes"] == []
        assert data["edges"] == []
