"""Unit tests for dev_routes graph viewer multi-tenant support.

Tests that the graph viewer data endpoint accepts a graph_name query
parameter and that available AGE graphs can be listed.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrastructure.dependencies import get_age_connection_pool
from util.dev_routes import router


@pytest.fixture
def mock_pool():
    """Create a mock connection pool."""
    pool = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()

    pool.get_connection.return_value = conn
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # Attach cursor for test-specific configuration
    pool._test_cursor = cursor
    return pool


@pytest.fixture
def app(mock_pool):
    """Create a FastAPI app with dev routes and mocked pool dependency."""
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_age_connection_pool] = lambda: mock_pool
    return test_app


@pytest.fixture
def client(app):
    """Create a test client for the dev routes."""
    return TestClient(app)


class TestListGraphs:
    """Tests for the /util/graphs endpoint that lists available AGE graphs."""

    def test_returns_list_of_graphs(self, client, mock_pool):
        """Should return a list of available AGE graph names."""
        mock_pool._test_cursor.fetchall.return_value = [
            ("tenant_a_graph",),
            ("tenant_b_graph",),
            ("kartograph_graph",),
        ]

        response = client.get("/util/graphs")

        assert response.status_code == 200
        data = response.json()
        assert "graphs" in data
        assert data["graphs"] == [
            "tenant_a_graph",
            "tenant_b_graph",
            "kartograph_graph",
        ]

    def test_returns_empty_list_when_no_graphs(self, client, mock_pool):
        """Should return empty list when no AGE graphs exist."""
        mock_pool._test_cursor.fetchall.return_value = []

        response = client.get("/util/graphs")

        assert response.status_code == 200
        assert response.json() == {"graphs": []}


class TestGraphViewerDataWithGraphName:
    """Tests for the /util/graph-viewer/data endpoint with graph_name parameter."""

    def test_uses_query_param_graph_name(self, client, mock_pool):
        """Should use the graph_name query parameter when provided."""
        with patch("util.dev_routes._fetch_graph_data") as mock_fetch:
            mock_fetch.return_value = {"nodes": [], "edges": []}
            response = client.get("/util/graph-viewer/data?graph_name=my_custom_graph")

        assert response.status_code == 200
        mock_fetch.assert_called_once_with(mock_pool, "my_custom_graph")

    def test_falls_back_to_default_graph_name(self, client, mock_pool):
        """Should fall back to settings.graph_name when no query param provided."""
        with (
            patch("util.dev_routes._fetch_graph_data") as mock_fetch,
            patch("util.dev_routes.get_database_settings") as mock_settings,
        ):
            mock_settings.return_value.graph_name = "default_graph"
            mock_fetch.return_value = {"nodes": [], "edges": []}
            response = client.get("/util/graph-viewer/data")

        assert response.status_code == 200
        mock_fetch.assert_called_once_with(mock_pool, "default_graph")

    def test_rejects_graph_name_with_special_characters(self, client):
        """Should reject graph names containing SQL-unsafe characters."""
        response = client.get("/util/graph-viewer/data?graph_name=graph'; DROP TABLE--")

        assert response.status_code == 400
        assert "alphanumeric" in response.json()["detail"]

    def test_rejects_empty_graph_name(self, client):
        """Should reject empty graph name."""
        response = client.get("/util/graph-viewer/data?graph_name=")

        assert response.status_code == 400


class TestGraphViewerTemplateIncludesGraphPicker:
    """Tests that the graph viewer HTML includes graph selection UI."""

    def test_viewer_page_returns_html(self, client):
        """Graph viewer page should return HTML."""
        response = client.get("/util/graph-viewer")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_viewer_page_contains_graph_selector(self, client):
        """Graph viewer HTML should contain a graph selector element."""
        response = client.get("/util/graph-viewer")
        html = response.text
        assert "graphSelector" in html or "graph-selector" in html
