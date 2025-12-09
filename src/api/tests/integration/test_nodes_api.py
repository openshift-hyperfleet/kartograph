"""Integration tests for node management API endpoints.

Tests CRUD operations on graph nodes via REST API.

Run with: pytest -m integration tests/integration/test_nodes_api.py
Requires: Running PostgreSQL with AGE extension
"""

import os

import pytest
from fastapi.testclient import TestClient

from main import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def test_client():
    """Create a test client for the FastAPI app."""
    # Set environment variables for test database connection
    os.environ.setdefault("KARTOGRAPH_DB_HOST", "localhost")
    os.environ.setdefault("KARTOGRAPH_DB_PORT", "5432")
    os.environ.setdefault("KARTOGRAPH_DB_DATABASE", "kartograph")
    os.environ.setdefault("KARTOGRAPH_DB_USERNAME", "kartograph")
    os.environ.setdefault("KARTOGRAPH_DB_PASSWORD", "kartograph_dev_password")
    os.environ.setdefault("KARTOGRAPH_DB_GRAPH_NAME", "test_graph")

    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_graph_via_api(test_client):
    """Clean the graph before and after each test via API."""
    # Clean before test
    test_client.delete("/nodes")
    yield
    # Clean after test
    test_client.delete("/nodes")


class TestNodeCreation:
    """Tests for POST /nodes endpoint."""

    def test_create_nodes_returns_201(self, test_client):
        """Creating nodes should return 201 status."""
        response = test_client.post("/nodes?count=5")
        assert response.status_code == 201

    def test_create_nodes_returns_count(self, test_client):
        """Response should include count of nodes created."""
        response = test_client.post("/nodes?count=3")
        data = response.json()
        assert "count" in data
        assert data["count"] == 3

    def test_create_nodes_with_default_count(self, test_client):
        """Should create 1 node by default if count not specified."""
        response = test_client.post("/nodes")
        assert response.status_code == 201
        data = response.json()
        assert data["count"] == 1

    def test_create_nodes_rejects_zero(self, test_client):
        """Should reject count of 0."""
        response = test_client.post("/nodes?count=0")
        assert response.status_code == 400

    def test_create_nodes_rejects_negative(self, test_client):
        """Should reject negative count."""
        response = test_client.post("/nodes?count=-5")
        assert response.status_code == 400


class TestNodeQuery:
    """Tests for GET /nodes endpoint."""

    def test_get_nodes_returns_200(self, test_client):
        """Querying nodes should return 200 status."""
        # Create some nodes
        test_client.post("/nodes?count=2")

        response = test_client.get("/nodes")
        assert response.status_code == 200

    def test_get_nodes_returns_list(self, test_client):
        """Response should include list of nodes."""
        # Create nodes
        test_client.post("/nodes?count=3")

        response = test_client.get("/nodes")
        data = response.json()
        assert "nodes" in data
        assert isinstance(data["nodes"], list)
        assert len(data["nodes"]) == 3

    def test_get_nodes_returns_count(self, test_client):
        """Response should include total count."""
        # Create nodes
        test_client.post("/nodes?count=5")

        response = test_client.get("/nodes")
        data = response.json()
        assert "count" in data
        assert data["count"] == 5

    def test_get_nodes_empty_graph(self, test_client):
        """Should return empty list for empty graph."""
        response = test_client.get("/nodes")
        data = response.json()
        assert data["nodes"] == []
        assert data["count"] == 0


class TestNodeDeletion:
    """Tests for DELETE /nodes endpoint."""

    def test_delete_nodes_returns_200(self, test_client):
        """Deleting nodes should return 200 status."""
        # Create some nodes first
        test_client.post("/nodes?count=3")

        response = test_client.delete("/nodes")
        assert response.status_code == 200

    def test_delete_nodes_returns_count(self, test_client):
        """Response should include count of deleted nodes."""
        # Create nodes
        test_client.post("/nodes?count=4")

        response = test_client.delete("/nodes")
        data = response.json()
        assert "deleted" in data
        assert data["deleted"] == 4

    def test_delete_nodes_empties_graph(self, test_client):
        """After deletion, graph should be empty."""
        # Create and then delete
        test_client.post("/nodes?count=5")
        test_client.delete("/nodes")

        # Verify empty
        response = test_client.get("/nodes")
        data = response.json()
        assert data["count"] == 0

    def test_delete_nodes_on_empty_graph(self, test_client):
        """Deleting from empty graph should succeed."""
        # Delete on empty graph
        response = test_client.delete("/nodes")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 0
