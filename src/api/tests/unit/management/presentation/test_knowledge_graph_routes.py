"""Unit tests for Knowledge Graph route handlers.

Tests route-level behavior including status codes, response shapes,
error handling, and pagination. Service dependencies are mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId
from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    UnauthorizedError,
)

# Fixed test data
TENANT_ID = "test-tenant-id"
WORKSPACE_ID = "test-workspace-id"
USER_ID = "test-user-id"
KG_ID = "01JTEST00000000000000KG001"
NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _make_current_user() -> CurrentUser:
    """Create a CurrentUser for dependency override."""
    return CurrentUser(
        user_id=UserId(value=USER_ID),
        username="testuser",
        tenant_id=TenantId(value=TENANT_ID),
    )


def _make_kg(
    kg_id: str = KG_ID,
    name: str = "Test KG",
    description: str = "A test knowledge graph",
) -> KnowledgeGraph:
    """Create a KnowledgeGraph aggregate for testing."""
    return KnowledgeGraph(
        id=KnowledgeGraphId(value=kg_id),
        tenant_id=TENANT_ID,
        workspace_id=WORKSPACE_ID,
        name=name,
        description=description,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest_asyncio.fixture
async def mock_service():
    """Create a mock KnowledgeGraphService."""
    return AsyncMock()


@pytest_asyncio.fixture
async def client(mock_service):
    """Create an async HTTP client with mocked dependencies."""
    from main import app

    from iam.dependencies.user import get_current_user
    from management.dependencies.knowledge_graph import get_knowledge_graph_service

    app.dependency_overrides[get_current_user] = lambda: _make_current_user()
    app.dependency_overrides[get_knowledge_graph_service] = lambda: mock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


class TestCreateKnowledgeGraph:
    """Tests for POST /management/workspaces/{workspace_id}/knowledge-graphs."""

    @pytest.mark.asyncio
    async def test_creates_successfully(self, client, mock_service):
        """Test successful creation returns 201 with correct response shape."""
        kg = _make_kg()
        mock_service.create.return_value = kg

        resp = await client.post(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
            json={"name": "Test KG", "description": "A test knowledge graph"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == KG_ID
        assert data["tenant_id"] == TENANT_ID
        assert data["workspace_id"] == WORKSPACE_ID
        assert data["name"] == "Test KG"
        assert data["description"] == "A test knowledge graph"
        assert "created_at" in data
        assert "updated_at" in data

        mock_service.create.assert_awaited_once_with(
            user_id=USER_ID,
            workspace_id=WORKSPACE_ID,
            name="Test KG",
            description="A test knowledge graph",
        )

    @pytest.mark.asyncio
    async def test_default_description(self, client, mock_service):
        """Test that description defaults to empty string."""
        kg = _make_kg(description="")
        mock_service.create.return_value = kg

        resp = await client.post(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
            json={"name": "Test KG"},
        )

        assert resp.status_code == 201
        mock_service.create.assert_awaited_once_with(
            user_id=USER_ID,
            workspace_id=WORKSPACE_ID,
            name="Test KG",
            description="",
        )

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.create.side_effect = UnauthorizedError("denied")

        resp = await client.post(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
            json={"name": "Test KG"},
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_duplicate_name_returns_409(self, client, mock_service):
        """Test that DuplicateKnowledgeGraphNameError maps to 409."""
        mock_service.create.side_effect = DuplicateKnowledgeGraphNameError("dup")

        resp = await client.post(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
            json={"name": "Test KG"},
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_empty_name_returns_422(self, client, mock_service):
        """Test that Pydantic validation rejects empty name."""
        resp = await client.post(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
            json={"name": ""},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_name_too_long_returns_422(self, client, mock_service):
        """Test that Pydantic validation rejects names over 100 characters."""
        resp = await client.post(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
            json={"name": "x" * 101},
        )

        assert resp.status_code == 422


class TestListKnowledgeGraphs:
    """Tests for GET /management/workspaces/{workspace_id}/knowledge-graphs."""

    @pytest.mark.asyncio
    async def test_lists_successfully(self, client, mock_service):
        """Test successful list returns 200 with correct pagination."""
        kgs = [_make_kg(kg_id=f"01JTEST00000000000000KG00{i}") for i in range(3)]
        mock_service.list_for_workspace.return_value = (kgs, 3)

        resp = await client.get(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["offset"] == 0
        assert data["limit"] == 20

    @pytest.mark.asyncio
    async def test_pagination_offset_limit(self, client, mock_service):
        """Test that offset and limit query params work correctly."""
        # Service returns only the paginated slice; total reflects full count
        kgs = [_make_kg(kg_id=f"01JTEST00000000000000KG00{i}") for i in range(2)]
        mock_service.list_for_workspace.return_value = (kgs, 5)

        resp = await client.get(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs?offset=1&limit=2",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["offset"] == 1
        assert data["limit"] == 2

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.list_for_workspace.side_effect = UnauthorizedError("denied")

        resp = await client.get(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_list(self, client, mock_service):
        """Test listing returns empty result correctly."""
        mock_service.list_for_workspace.return_value = ([], 0)

        resp = await client.get(
            f"/management/workspaces/{WORKSPACE_ID}/knowledge-graphs",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestGetKnowledgeGraph:
    """Tests for GET /management/knowledge-graphs/{kg_id}."""

    @pytest.mark.asyncio
    async def test_gets_successfully(self, client, mock_service):
        """Test successful get returns 200 with correct response."""
        kg = _make_kg()
        mock_service.get.return_value = kg

        resp = await client.get(f"/management/knowledge-graphs/{KG_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == KG_ID
        assert data["name"] == "Test KG"

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client, mock_service):
        """Test that None from service maps to 404."""
        mock_service.get.return_value = None

        resp = await client.get(f"/management/knowledge-graphs/{KG_ID}")

        assert resp.status_code == 404


class TestUpdateKnowledgeGraph:
    """Tests for PATCH /management/knowledge-graphs/{kg_id}."""

    @pytest.mark.asyncio
    async def test_updates_successfully(self, client, mock_service):
        """Test successful update returns 200 with updated data."""
        kg = _make_kg(name="Updated KG")
        mock_service.update.return_value = kg

        resp = await client.patch(
            f"/management/knowledge-graphs/{KG_ID}",
            json={"name": "Updated KG"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated KG"

        mock_service.update.assert_awaited_once_with(
            user_id=USER_ID,
            kg_id=KG_ID,
            name="Updated KG",
            description=None,
        )

    @pytest.mark.asyncio
    async def test_partial_update_description_only(self, client, mock_service):
        """Test updating only description passes None for name."""
        kg = _make_kg(description="New desc")
        mock_service.update.return_value = kg

        resp = await client.patch(
            f"/management/knowledge-graphs/{KG_ID}",
            json={"description": "New desc"},
        )

        assert resp.status_code == 200
        mock_service.update.assert_awaited_once_with(
            user_id=USER_ID,
            kg_id=KG_ID,
            name=None,
            description="New desc",
        )

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.update.side_effect = UnauthorizedError("denied")

        resp = await client.patch(
            f"/management/knowledge-graphs/{KG_ID}",
            json={"name": "New Name"},
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_duplicate_name_returns_409(self, client, mock_service):
        """Test that DuplicateKnowledgeGraphNameError maps to 409."""
        mock_service.update.side_effect = DuplicateKnowledgeGraphNameError("dup")

        resp = await client.patch(
            f"/management/knowledge-graphs/{KG_ID}",
            json={"name": "Existing Name"},
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client, mock_service):
        """Test that ValueError with 'not found' from service maps to 404."""
        mock_service.update.side_effect = ValueError("not found")

        resp = await client.patch(
            f"/management/knowledge-graphs/{KG_ID}",
            json={"name": "New Name"},
        )

        assert resp.status_code == 404


class TestDeleteKnowledgeGraph:
    """Tests for DELETE /management/knowledge-graphs/{kg_id}."""

    @pytest.mark.asyncio
    async def test_deletes_successfully(self, client, mock_service):
        """Test successful delete returns 204."""
        mock_service.delete.return_value = True

        resp = await client.delete(f"/management/knowledge-graphs/{KG_ID}")

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client, mock_service):
        """Test that False from service maps to 404."""
        mock_service.delete.return_value = False

        resp = await client.delete(f"/management/knowledge-graphs/{KG_ID}")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.delete.side_effect = UnauthorizedError("denied")

        resp = await client.delete(f"/management/knowledge-graphs/{KG_ID}")

        assert resp.status_code == 403
