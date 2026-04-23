"""Unit tests for Knowledge Graph HTTP routes.

Tests the presentation layer for knowledge graph endpoints in the Management
bounded context. Follows the same patterns as IAM workspace route tests.

Scenarios covered (per spec: specs/management/knowledge-graphs.spec.md):
- Create: 201 success, 403 unauthorized, 409 duplicate, 422 invalid, 401 unauthenticated
- Get: 200 success, 404 not-found/unauthorized (no distinction), 401 unauthenticated
- List for workspace: 200 success, 403 unauthorized, 401 unauthenticated
- Update: 200 success, 403 unauthorized, 404 not-found, 409 duplicate, 422 invalid,
          401 unauthenticated
- Delete: 204 success, 403 unauthorized, 404 not-found, 401 unauthenticated
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    UnauthorizedError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_kg(
    kg_id: str = "01JT0000000000000000000001",
    tenant_id: str = "tenant-123",
    workspace_id: str = "01JT0000000000000000000002",
    name: str = "Platform Graph",
    description: str = "A test knowledge graph",
) -> KnowledgeGraph:
    """Create a KnowledgeGraph domain object for testing."""
    now = datetime.now(UTC)
    kg = KnowledgeGraph(
        id=KnowledgeGraphId(value=kg_id),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        name=name,
        description=description,
        created_at=now,
        updated_at=now,
    )
    kg.collect_events()
    return kg


@pytest.fixture
def mock_kg_service() -> AsyncMock:
    """Mock KnowledgeGraphService for testing."""
    return AsyncMock(spec=KnowledgeGraphService)


@pytest.fixture
def mock_current_user() -> CurrentUser:
    """Mock CurrentUser for authentication."""
    return CurrentUser(
        user_id=UserId(value="01JT0000000000000000000099"),
        username="testuser",
        tenant_id=TenantId(value="tenant-123"),
    )


@pytest.fixture
def test_client(
    mock_kg_service: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies.user import get_current_user
    from management.dependencies.knowledge_graph import get_knowledge_graph_service
    from management.presentation import router

    app = FastAPI()
    app.dependency_overrides[get_knowledge_graph_service] = lambda: mock_kg_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def unauthenticated_test_client(
    mock_kg_service: AsyncMock,
) -> TestClient:
    """Create TestClient that simulates unauthenticated requests."""
    from fastapi import HTTPException

    from iam.dependencies.user import get_current_user
    from management.dependencies.knowledge_graph import get_knowledge_graph_service
    from management.presentation import router

    async def raise_unauthorized() -> CurrentUser:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer, API-Key"},
        )

    app = FastAPI()
    app.dependency_overrides[get_knowledge_graph_service] = lambda: mock_kg_service
    app.dependency_overrides[get_current_user] = raise_unauthorized
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Create Knowledge Graph: POST /management/workspaces/{ws_id}/knowledge-graphs
# ---------------------------------------------------------------------------


class TestCreateKnowledgeGraph:
    """Tests for POST /management/workspaces/{workspace_id}/knowledge-graphs."""

    def test_create_knowledge_graph_returns_201(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Successful creation returns 201 with full knowledge graph details."""
        workspace_id = "01JT0000000000000000000002"
        kg = _make_kg(workspace_id=workspace_id)
        mock_kg_service.create.return_value = kg

        response = test_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            json={"name": "Platform Graph", "description": "A test knowledge graph"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["id"] == kg.id.value
        assert result["tenant_id"] == kg.tenant_id
        assert result["workspace_id"] == kg.workspace_id
        assert result["name"] == "Platform Graph"
        assert result["description"] == "A test knowledge graph"
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_knowledge_graph_calls_service_with_correct_args(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """The route passes workspace_id, name, description, and user_id to the service."""
        workspace_id = "01JT0000000000000000000002"
        mock_kg_service.create.return_value = _make_kg(workspace_id=workspace_id)

        test_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            json={"name": "My Graph", "description": "desc"},
        )

        mock_kg_service.create.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            workspace_id=workspace_id,
            name="My Graph",
            description="desc",
        )

    def test_create_knowledge_graph_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 403 Forbidden when user lacks edit permission on the workspace."""
        workspace_id = "01JT0000000000000000000002"
        mock_kg_service.create.side_effect = UnauthorizedError(
            "User lacks edit permission"
        )

        response = test_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            json={"name": "Platform Graph", "description": "desc"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (
            response.json()["detail"]
            == "You do not have permission to perform this action"
        )

    def test_create_knowledge_graph_returns_409_for_duplicate_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 409 Conflict when knowledge graph name already exists in tenant."""
        workspace_id = "01JT0000000000000000000002"
        mock_kg_service.create.side_effect = DuplicateKnowledgeGraphNameError(
            "Knowledge graph 'Platform Graph' already exists in tenant"
        )

        response = test_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            json={"name": "Platform Graph", "description": "desc"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    def test_create_knowledge_graph_returns_422_for_empty_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 422 Unprocessable Entity when name is empty (Pydantic validation)."""
        workspace_id = "01JT0000000000000000000002"

        response = test_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            json={"name": "", "description": "desc"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_knowledge_graph_returns_422_for_oversized_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 422 Unprocessable Entity when name exceeds 100 characters."""
        workspace_id = "01JT0000000000000000000002"
        long_name = "x" * 101

        response = test_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            json={"name": long_name, "description": "desc"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_knowledge_graph_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Returns 401 Unauthorized when no credentials are provided."""
        workspace_id = "01JT0000000000000000000002"

        response = unauthenticated_test_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            json={"name": "Platform Graph", "description": "desc"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Get Knowledge Graph: GET /management/knowledge-graphs/{id}
# ---------------------------------------------------------------------------


class TestGetKnowledgeGraph:
    """Tests for GET /management/knowledge-graphs/{id}."""

    def test_get_knowledge_graph_returns_200(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Authorized retrieval returns 200 with knowledge graph details."""
        kg = _make_kg()
        mock_kg_service.get.return_value = kg

        response = test_client.get(f"/management/knowledge-graphs/{kg.id.value}")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["id"] == kg.id.value
        assert result["tenant_id"] == kg.tenant_id
        assert result["workspace_id"] == kg.workspace_id
        assert result["name"] == kg.name
        assert result["description"] == kg.description
        assert "created_at" in result
        assert "updated_at" in result

    def test_get_knowledge_graph_calls_service_with_correct_args(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Route passes kg_id and user_id to the service."""
        kg = _make_kg()
        mock_kg_service.get.return_value = kg

        test_client.get(f"/management/knowledge-graphs/{kg.id.value}")

        mock_kg_service.get.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=kg.id.value,
        )

    def test_get_knowledge_graph_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 404 when knowledge graph is not found."""
        mock_kg_service.get.return_value = None
        kg_id = "01JT0000000000000000000001"

        response = test_client.get(f"/management/knowledge-graphs/{kg_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_knowledge_graph_returns_404_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 404 (not 403) when caller lacks view access — no existence leakage.

        Per spec: no distinction between unauthorized and missing.
        Service returns None in both cases, route returns 404.
        """
        mock_kg_service.get.return_value = None
        kg_id = "01JT0000000000000000000001"

        response = test_client.get(f"/management/knowledge-graphs/{kg_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_knowledge_graph_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Returns 401 Unauthorized when no credentials are provided."""
        kg_id = "01JT0000000000000000000001"

        response = unauthenticated_test_client.get(
            f"/management/knowledge-graphs/{kg_id}"
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# List Knowledge Graphs: GET /management/workspaces/{ws_id}/knowledge-graphs
# ---------------------------------------------------------------------------


class TestListKnowledgeGraphs:
    """Tests for GET /management/workspaces/{workspace_id}/knowledge-graphs."""

    def test_list_knowledge_graphs_returns_200_with_list(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Authorized list returns 200 with knowledge graphs and count."""
        workspace_id = "01JT0000000000000000000002"
        kg1 = _make_kg(kg_id="01JT0000000000000000000001", name="Graph A")
        kg2 = _make_kg(kg_id="01JT0000000000000000000003", name="Graph B")
        mock_kg_service.list_for_workspace.return_value = [kg1, kg2]

        response = test_client.get(
            f"/management/workspaces/{workspace_id}/knowledge-graphs"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["count"] == 2
        assert len(result["knowledge_graphs"]) == 2
        assert result["knowledge_graphs"][0]["name"] == "Graph A"
        assert result["knowledge_graphs"][1]["name"] == "Graph B"

    def test_list_knowledge_graphs_returns_empty_list(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 200 with empty list when no knowledge graphs exist."""
        workspace_id = "01JT0000000000000000000002"
        mock_kg_service.list_for_workspace.return_value = []

        response = test_client.get(
            f"/management/workspaces/{workspace_id}/knowledge-graphs"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["count"] == 0
        assert result["knowledge_graphs"] == []

    def test_list_knowledge_graphs_calls_service_with_correct_args(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Route passes workspace_id and user_id to the service."""
        workspace_id = "01JT0000000000000000000002"
        mock_kg_service.list_for_workspace.return_value = []

        test_client.get(f"/management/workspaces/{workspace_id}/knowledge-graphs")

        mock_kg_service.list_for_workspace.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            workspace_id=workspace_id,
        )

    def test_list_knowledge_graphs_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 403 Forbidden when user lacks view permission on workspace."""
        workspace_id = "01JT0000000000000000000002"
        mock_kg_service.list_for_workspace.side_effect = UnauthorizedError(
            "User lacks view permission on workspace"
        )

        response = test_client.get(
            f"/management/workspaces/{workspace_id}/knowledge-graphs"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (
            response.json()["detail"]
            == "You do not have permission to perform this action"
        )

    def test_list_knowledge_graphs_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Returns 401 Unauthorized when no credentials are provided."""
        workspace_id = "01JT0000000000000000000002"

        response = unauthenticated_test_client.get(
            f"/management/workspaces/{workspace_id}/knowledge-graphs"
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Update Knowledge Graph: PATCH /management/knowledge-graphs/{id}
# ---------------------------------------------------------------------------


class TestUpdateKnowledgeGraph:
    """Tests for PATCH /management/knowledge-graphs/{id}."""

    def test_update_knowledge_graph_returns_200(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Successful update returns 200 with updated knowledge graph details."""
        kg = _make_kg(name="Updated Graph", description="Updated desc")
        mock_kg_service.update.return_value = kg

        response = test_client.patch(
            f"/management/knowledge-graphs/{kg.id.value}",
            json={"name": "Updated Graph", "description": "Updated desc"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["id"] == kg.id.value
        assert result["name"] == "Updated Graph"
        assert result["description"] == "Updated desc"

    def test_update_knowledge_graph_calls_service_with_correct_args(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Route passes kg_id, name, description, and user_id to the service."""
        kg = _make_kg()
        mock_kg_service.update.return_value = kg

        test_client.patch(
            f"/management/knowledge-graphs/{kg.id.value}",
            json={"name": "New Name", "description": "New desc"},
        )

        mock_kg_service.update.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=kg.id.value,
            name="New Name",
            description="New desc",
        )

    def test_update_knowledge_graph_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 403 Forbidden when user lacks edit permission on the knowledge graph."""
        kg_id = "01JT0000000000000000000001"
        mock_kg_service.update.side_effect = UnauthorizedError(
            "User lacks edit permission"
        )

        response = test_client.patch(
            f"/management/knowledge-graphs/{kg_id}",
            json={"name": "Updated", "description": "desc"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (
            response.json()["detail"]
            == "You do not have permission to perform this action"
        )

    def test_update_knowledge_graph_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 404 Not Found when knowledge graph does not exist."""
        kg_id = "01JT0000000000000000000001"
        mock_kg_service.update.side_effect = ValueError(
            f"Knowledge graph {kg_id} not found"
        )

        response = test_client.patch(
            f"/management/knowledge-graphs/{kg_id}",
            json={"name": "Updated", "description": "desc"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_update_knowledge_graph_returns_409_for_duplicate_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 409 Conflict when new name already exists in tenant."""
        kg_id = "01JT0000000000000000000001"
        mock_kg_service.update.side_effect = DuplicateKnowledgeGraphNameError(
            "Knowledge graph 'Existing Graph' already exists in tenant"
        )

        response = test_client.patch(
            f"/management/knowledge-graphs/{kg_id}",
            json={"name": "Existing Graph", "description": "desc"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    def test_update_knowledge_graph_returns_422_for_empty_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 422 Unprocessable Entity when name is empty (Pydantic validation)."""
        kg_id = "01JT0000000000000000000001"

        response = test_client.patch(
            f"/management/knowledge-graphs/{kg_id}",
            json={"name": "", "description": "desc"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_update_knowledge_graph_returns_422_for_oversized_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 422 when name exceeds 100 characters."""
        kg_id = "01JT0000000000000000000001"
        long_name = "x" * 101

        response = test_client.patch(
            f"/management/knowledge-graphs/{kg_id}",
            json={"name": long_name, "description": "desc"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_update_knowledge_graph_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Returns 401 Unauthorized when no credentials are provided."""
        kg_id = "01JT0000000000000000000001"

        response = unauthenticated_test_client.patch(
            f"/management/knowledge-graphs/{kg_id}",
            json={"name": "Updated", "description": "desc"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Delete Knowledge Graph: DELETE /management/knowledge-graphs/{id}
# ---------------------------------------------------------------------------


class TestDeleteKnowledgeGraph:
    """Tests for DELETE /management/knowledge-graphs/{id}."""

    def test_delete_knowledge_graph_returns_204(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Successful deletion returns 204 No Content with empty body."""
        kg_id = "01JT0000000000000000000001"
        mock_kg_service.delete.return_value = True

        response = test_client.delete(f"/management/knowledge-graphs/{kg_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

    def test_delete_knowledge_graph_calls_service_with_correct_args(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Route passes kg_id and user_id to the service."""
        kg_id = "01JT0000000000000000000001"
        mock_kg_service.delete.return_value = True

        test_client.delete(f"/management/knowledge-graphs/{kg_id}")

        mock_kg_service.delete.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=kg_id,
        )

    def test_delete_knowledge_graph_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 403 Forbidden when user lacks manage permission."""
        kg_id = "01JT0000000000000000000001"
        mock_kg_service.delete.side_effect = UnauthorizedError(
            "User lacks manage permission"
        )

        response = test_client.delete(f"/management/knowledge-graphs/{kg_id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (
            response.json()["detail"]
            == "You do not have permission to perform this action"
        )

    def test_delete_knowledge_graph_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Returns 404 Not Found when service returns False (KG not found)."""
        kg_id = "01JT0000000000000000000001"
        mock_kg_service.delete.return_value = False

        response = test_client.delete(f"/management/knowledge-graphs/{kg_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_delete_knowledge_graph_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Returns 401 Unauthorized when no credentials are provided."""
        kg_id = "01JT0000000000000000000001"

        response = unauthenticated_test_client.delete(
            f"/management/knowledge-graphs/{kg_id}"
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
