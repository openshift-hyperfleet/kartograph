"""Unit tests for Knowledge Graph HTTP routes.

Tests the Management presentation layer for knowledge graph endpoints
following the patterns established in tests/unit/iam/presentation/.
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
    KnowledgeGraphNotFoundError,
    UnauthorizedError,
)


@pytest.fixture
def mock_kg_service() -> AsyncMock:
    """Mock KnowledgeGraphService for testing."""
    return AsyncMock(spec=KnowledgeGraphService)


@pytest.fixture
def mock_current_user() -> CurrentUser:
    """Mock CurrentUser for authentication."""
    return CurrentUser(
        user_id=UserId(value="01JPQRST1234567890ABCDEFGH"),
        username="testuser",
        tenant_id=TenantId(value="01JPQRST1234567890ABCDEFAB"),
    )


@pytest.fixture
def sample_knowledge_graph(mock_current_user: CurrentUser) -> KnowledgeGraph:
    """Create a sample KnowledgeGraph for testing."""
    now = datetime.now(UTC)
    return KnowledgeGraph(
        id=KnowledgeGraphId(value="01JPQRST1234567890ABCDEFKG"),
        tenant_id=mock_current_user.tenant_id.value,
        workspace_id="01JPQRST1234567890ABCDEFWS",
        name="My Knowledge Graph",
        description="A test knowledge graph",
        created_at=now,
        updated_at=now,
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


class TestListKnowledgeGraphsRoute:
    """Tests for GET /management/knowledge-graphs endpoint."""

    def test_list_knowledge_graphs_returns_200(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should return 200 with list of KGs the user can view."""
        mock_kg_service.list_all.return_value = [sample_knowledge_graph]

        response = test_client.get("/management/knowledge-graphs")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert "knowledge_graphs" in result
        assert len(result["knowledge_graphs"]) == 1
        assert result["knowledge_graphs"][0]["id"] == sample_knowledge_graph.id.value
        assert result["knowledge_graphs"][0]["name"] == sample_knowledge_graph.name

    def test_list_knowledge_graphs_calls_list_all(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call service.list_all with the current user's ID."""
        mock_kg_service.list_all.return_value = []

        test_client.get("/management/knowledge-graphs")

        mock_kg_service.list_all.assert_called_once_with(
            user_id=mock_current_user.user_id.value
        )

    def test_list_knowledge_graphs_returns_empty_list(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Should return empty list when no KGs exist."""
        mock_kg_service.list_all.return_value = []

        response = test_client.get("/management/knowledge-graphs")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["knowledge_graphs"] == []


class TestGetKnowledgeGraphRoute:
    """Tests for GET /management/knowledge-graphs/{kg_id} endpoint."""

    def test_get_knowledge_graph_returns_200(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should return 200 with KG details when found."""
        mock_kg_service.get.return_value = sample_knowledge_graph

        response = test_client.get(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["id"] == sample_knowledge_graph.id.value
        assert result["name"] == sample_knowledge_graph.name
        assert result["description"] == sample_knowledge_graph.description
        assert result["tenant_id"] == sample_knowledge_graph.tenant_id
        assert result["workspace_id"] == sample_knowledge_graph.workspace_id

    def test_get_knowledge_graph_calls_service_with_user_id(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call the service with the current user's ID."""
        mock_kg_service.get.return_value = sample_knowledge_graph

        test_client.get(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}"
        )

        mock_kg_service.get.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=sample_knowledge_graph.id.value,
        )

    def test_get_knowledge_graph_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Should return 404 when KG is not found (service returns None)."""
        mock_kg_service.get.return_value = None

        response = test_client.get(
            "/management/knowledge-graphs/01JPQRST1234567890ABCDEFKG"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCreateKnowledgeGraphRoute:
    """Tests for POST /management/workspaces/{workspace_id}/knowledge-graphs endpoint."""

    def test_create_knowledge_graph_returns_201(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should create KG and return 201 with KG details."""
        mock_kg_service.create.return_value = sample_knowledge_graph

        response = test_client.post(
            "/management/workspaces/01JPQRST1234567890ABCDEFWS/knowledge-graphs",
            json={
                "name": "My Knowledge Graph",
                "description": "A test knowledge graph",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["id"] == sample_knowledge_graph.id.value
        assert result["name"] == sample_knowledge_graph.name
        assert result["description"] == sample_knowledge_graph.description

    def test_create_knowledge_graph_calls_service_correctly(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call the service with correct parameters."""
        mock_kg_service.create.return_value = sample_knowledge_graph
        workspace_id = "01JPQRST1234567890ABCDEFWS"

        test_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            json={"name": "My Knowledge Graph", "description": "A test KG"},
        )

        mock_kg_service.create.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            workspace_id=workspace_id,
            name="My Knowledge Graph",
            description="A test KG",
        )

    def test_create_knowledge_graph_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Should return 403 when service raises UnauthorizedError."""
        mock_kg_service.create.side_effect = UnauthorizedError(
            "User lacks edit permission on workspace"
        )

        response = test_client.post(
            "/management/workspaces/01JPQRST1234567890ABCDEFWS/knowledge-graphs",
            json={"name": "My Knowledge Graph", "description": ""},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "permission" in response.json()["detail"].lower()

    def test_create_knowledge_graph_returns_409_on_duplicate_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Should return 409 when KG name already exists in tenant."""
        mock_kg_service.create.side_effect = DuplicateKnowledgeGraphNameError(
            "Knowledge graph 'My Knowledge Graph' already exists in tenant"
        )

        response = test_client.post(
            "/management/workspaces/01JPQRST1234567890ABCDEFWS/knowledge-graphs",
            json={"name": "My Knowledge Graph", "description": ""},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    def test_create_knowledge_graph_requires_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Should return 422 when name field is missing."""
        response = test_client.post(
            "/management/workspaces/01JPQRST1234567890ABCDEFWS/knowledge-graphs",
            json={"description": "No name provided"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_knowledge_graph_description_optional(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should succeed when description is omitted (defaults to empty string)."""
        mock_kg_service.create.return_value = sample_knowledge_graph

        response = test_client.post(
            "/management/workspaces/01JPQRST1234567890ABCDEFWS/knowledge-graphs",
            json={"name": "My Knowledge Graph"},
        )

        assert response.status_code == status.HTTP_201_CREATED


class TestListWorkspaceKnowledgeGraphsRoute:
    """Tests for GET /management/workspaces/{workspace_id}/knowledge-graphs endpoint."""

    def test_list_workspace_kgs_returns_200(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 200 with list of KGs in workspace."""
        mock_kg_service.list_for_workspace.return_value = [sample_knowledge_graph]

        response = test_client.get(
            "/management/workspaces/01JPQRST1234567890ABCDEFWS/knowledge-graphs"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert "knowledge_graphs" in result
        assert len(result["knowledge_graphs"]) == 1
        assert result["knowledge_graphs"][0]["id"] == sample_knowledge_graph.id.value

    def test_list_workspace_kgs_calls_service_with_correct_args(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call service.list_for_workspace with user_id and workspace_id."""
        mock_kg_service.list_for_workspace.return_value = []
        workspace_id = "01JPQRST1234567890ABCDEFWS"

        test_client.get(f"/management/workspaces/{workspace_id}/knowledge-graphs")

        mock_kg_service.list_for_workspace.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            workspace_id=workspace_id,
        )

    def test_list_workspace_kgs_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Should return 403 when user lacks view permission on workspace."""
        mock_kg_service.list_for_workspace.side_effect = UnauthorizedError(
            "User lacks view permission on workspace"
        )

        response = test_client.get(
            "/management/workspaces/01JPQRST1234567890ABCDEFWS/knowledge-graphs"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_workspace_kgs_returns_empty_list(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
    ) -> None:
        """Should return empty list when workspace has no visible KGs."""
        mock_kg_service.list_for_workspace.return_value = []

        response = test_client.get(
            "/management/workspaces/01JPQRST1234567890ABCDEFWS/knowledge-graphs"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["knowledge_graphs"] == []
        assert result["count"] == 0


class TestUpdateKnowledgeGraphRoute:
    """Tests for PATCH /management/knowledge-graphs/{kg_id} endpoint."""

    def test_update_knowledge_graph_returns_200(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 200 with updated KG when service.update succeeds."""
        mock_kg_service.update.return_value = sample_knowledge_graph

        response = test_client.patch(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}",
            json={"name": "Updated Name", "description": "Updated desc"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["id"] == sample_knowledge_graph.id.value

    def test_update_knowledge_graph_calls_service_with_correct_args(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call service.update with user_id, kg_id, name, and description."""
        mock_kg_service.update.return_value = sample_knowledge_graph
        kg_id = sample_knowledge_graph.id.value

        test_client.patch(
            f"/management/knowledge-graphs/{kg_id}",
            json={"name": "New Name", "description": "New desc"},
        )

        mock_kg_service.update.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=kg_id,
            name="New Name",
            description="New desc",
        )

    def test_update_knowledge_graph_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 403 when service raises UnauthorizedError."""
        mock_kg_service.update.side_effect = UnauthorizedError(
            "User lacks edit permission"
        )

        response = test_client.patch(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}",
            json={"name": "Updated Name", "description": ""},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_knowledge_graph_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 404 when service raises KnowledgeGraphNotFoundError."""
        mock_kg_service.update.side_effect = KnowledgeGraphNotFoundError(
            "Knowledge graph not found"
        )

        response = test_client.patch(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}",
            json={"name": "Updated Name", "description": ""},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_knowledge_graph_returns_409_on_duplicate_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 409 when service raises DuplicateKnowledgeGraphNameError."""
        mock_kg_service.update.side_effect = DuplicateKnowledgeGraphNameError(
            "Knowledge graph name already exists"
        )

        response = test_client.patch(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}",
            json={"name": "Duplicate Name", "description": ""},
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_update_knowledge_graph_requires_name(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 422 when name field is missing."""
        response = test_client.patch(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}",
            json={"description": "No name"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestDeleteKnowledgeGraphRoute:
    """Tests for DELETE /management/knowledge-graphs/{kg_id} endpoint."""

    def test_delete_knowledge_graph_returns_204(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 204 when KG is successfully deleted."""
        mock_kg_service.delete.return_value = True

        response = test_client.delete(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_knowledge_graph_calls_service_with_correct_args(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call service.delete with user_id and kg_id."""
        mock_kg_service.delete.return_value = True
        kg_id = sample_knowledge_graph.id.value

        test_client.delete(f"/management/knowledge-graphs/{kg_id}")

        mock_kg_service.delete.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=kg_id,
        )

    def test_delete_knowledge_graph_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 404 when service returns False (KG not found)."""
        mock_kg_service.delete.return_value = False

        response = test_client.delete(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_knowledge_graph_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_kg_service: AsyncMock,
        sample_knowledge_graph: KnowledgeGraph,
    ) -> None:
        """Should return 403 when service raises UnauthorizedError."""
        mock_kg_service.delete.side_effect = UnauthorizedError(
            "User lacks manage permission"
        )

        response = test_client.delete(
            f"/management/knowledge-graphs/{sample_knowledge_graph.id.value}"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
