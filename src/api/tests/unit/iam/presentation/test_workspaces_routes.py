"""Unit tests for Workspace HTTP routes.

Tests the presentation layer for workspace endpoints following
the patterns established in iam/presentation/test_api_key_routes.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import WorkspaceService
from iam.application.value_objects import CurrentUser
from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId, UserId, WorkspaceId
from iam.ports.exceptions import (
    CannotDeleteRootWorkspaceError,
    DuplicateWorkspaceNameError,
    UnauthorizedError,
    WorkspaceHasChildrenError,
)


@pytest.fixture
def mock_workspace_service() -> AsyncMock:
    """Mock WorkspaceService for testing."""
    return AsyncMock(spec=WorkspaceService)


@pytest.fixture
def mock_current_user() -> CurrentUser:
    """Mock CurrentUser for authentication."""
    return CurrentUser(
        user_id=UserId(value="test-user-123"),
        username="testuser",
        tenant_id=TenantId.generate(),
    )


@pytest.fixture
def root_workspace(mock_current_user: CurrentUser) -> Workspace:
    """Create a root workspace for use as parent in tests."""
    now = datetime.now(UTC)
    return Workspace(
        id=WorkspaceId.generate(),
        tenant_id=mock_current_user.tenant_id,
        name="Root",
        parent_workspace_id=None,
        is_root=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def child_workspace(
    mock_current_user: CurrentUser, root_workspace: Workspace
) -> Workspace:
    """Create a child workspace for testing."""
    now = datetime.now(UTC)
    return Workspace(
        id=WorkspaceId.generate(),
        tenant_id=mock_current_user.tenant_id,
        name="Engineering",
        parent_workspace_id=root_workspace.id,
        is_root=False,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def test_client(
    mock_workspace_service: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies.user import get_current_user
    from iam.dependencies.workspace import get_workspace_service
    from iam.presentation import router

    app = FastAPI()

    # Override dependencies with mocks
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    app.include_router(router)

    return TestClient(app)


@pytest.fixture
def unauthenticated_test_client(
    mock_workspace_service: AsyncMock,
) -> TestClient:
    """Create TestClient that simulates unauthenticated requests.

    Overrides get_current_user to raise 401, simulating what the real
    auth dependency does when no credentials are provided.
    """
    from fastapi import HTTPException

    from iam.dependencies.user import get_current_user
    from iam.dependencies.workspace import get_workspace_service
    from iam.presentation import router

    async def raise_unauthorized() -> CurrentUser:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer, API-Key"},
        )

    app = FastAPI()

    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_current_user] = raise_unauthorized

    app.include_router(router)

    return TestClient(app, raise_server_exceptions=False)


class TestCreateWorkspace:
    """Tests for POST /iam/workspaces endpoint."""

    def test_create_workspace_returns_201(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        root_workspace: Workspace,
        child_workspace: Workspace,
    ) -> None:
        """Test POST /workspaces returns 201 with workspace details."""
        mock_workspace_service.create_workspace.return_value = child_workspace

        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": root_workspace.id.value,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["id"] == child_workspace.id.value
        assert result["tenant_id"] == child_workspace.tenant_id.value
        assert result["name"] == "Engineering"
        assert result["parent_workspace_id"] == root_workspace.id.value
        assert result["is_root"] is False
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_workspace_returns_409_for_duplicate_name(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        root_workspace: Workspace,
    ) -> None:
        """Test POST /workspaces returns 409 when name already exists."""
        mock_workspace_service.create_workspace.side_effect = (
            DuplicateWorkspaceNameError(
                "Workspace 'Engineering' already exists in tenant"
            )
        )

        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": root_workspace.id.value,
            },
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    def test_create_workspace_returns_400_for_invalid_parent(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test POST /workspaces returns 400 when parent doesn't exist."""
        fake_parent_id = WorkspaceId.generate().value
        mock_workspace_service.create_workspace.side_effect = ValueError(
            f"Parent workspace {fake_parent_id} does not exist"
        )

        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": fake_parent_id,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not exist" in response.json()["detail"]

    def test_create_workspace_returns_422_for_invalid_name(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        root_workspace: Workspace,
    ) -> None:
        """Test POST /workspaces returns 422 for validation errors."""
        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "",
                "parent_workspace_id": root_workspace.id.value,
            },
        )

        # Pydantic validation catches empty name (min_length=1)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_workspace_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Test POST /workspaces returns 401 without authentication."""
        fake_parent_id = WorkspaceId.generate().value

        response = unauthenticated_test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": fake_parent_id,
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetWorkspace:
    """Tests for GET /iam/workspaces/{id} endpoint."""

    def test_get_workspace_returns_200(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        child_workspace: Workspace,
    ) -> None:
        """Test GET /workspaces/{id} returns 200 with workspace details."""
        mock_workspace_service.get_workspace.return_value = child_workspace

        response = test_client.get(
            f"/iam/workspaces/{child_workspace.id.value}",
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["id"] == child_workspace.id.value
        assert result["tenant_id"] == child_workspace.tenant_id.value
        assert result["name"] == child_workspace.name
        assert child_workspace.parent_workspace_id is not None
        assert (
            result["parent_workspace_id"] == child_workspace.parent_workspace_id.value
        )
        assert result["is_root"] is False
        assert "created_at" in result
        assert "updated_at" in result

    def test_get_workspace_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test GET /workspaces/{id} returns 404 when workspace doesn't exist."""
        mock_workspace_service.get_workspace.return_value = None
        random_id = WorkspaceId.generate().value

        response = test_client.get(
            f"/iam/workspaces/{random_id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_workspace_returns_404_for_different_tenant(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test GET /workspaces/{id} returns 404 for workspace in different tenant.

        The service returns None for cross-tenant workspaces (don't leak existence),
        so the route should return 404 just like a missing workspace.
        """
        mock_workspace_service.get_workspace.return_value = None
        cross_tenant_workspace_id = WorkspaceId.generate().value

        response = test_client.get(
            f"/iam/workspaces/{cross_tenant_workspace_id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_workspace_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Test GET /workspaces/{id} returns 401 without authentication."""
        random_id = WorkspaceId.generate().value

        response = unauthenticated_test_client.get(
            f"/iam/workspaces/{random_id}",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestListWorkspaces:
    """Tests for GET /iam/workspaces endpoint."""

    def test_list_workspaces_returns_200_with_all_workspaces(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        mock_current_user: CurrentUser,
        root_workspace: Workspace,
        child_workspace: Workspace,
    ) -> None:
        """Test GET /workspaces returns 200 with all workspaces in tenant."""
        now = datetime.now(UTC)
        second_child = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=mock_current_user.tenant_id,
            name="Marketing",
            parent_workspace_id=root_workspace.id,
            is_root=False,
            created_at=now,
            updated_at=now,
        )
        all_workspaces = [root_workspace, child_workspace, second_child]
        mock_workspace_service.list_workspaces.return_value = all_workspaces

        response = test_client.get("/iam/workspaces")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["count"] == 3
        assert len(result["workspaces"]) == 3
        # All workspaces should have the same tenant_id
        for ws in result["workspaces"]:
            assert ws["tenant_id"] == mock_current_user.tenant_id.value

    def test_list_workspaces_returns_empty_list(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test GET /workspaces returns 200 with empty list when tenant has no workspaces."""
        mock_workspace_service.list_workspaces.return_value = []

        response = test_client.get("/iam/workspaces")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["workspaces"] == []
        assert result["count"] == 0

    def test_list_workspaces_scoped_to_tenant(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Test GET /workspaces only returns workspaces from user's tenant.

        The service handles tenant scoping, so the route delegates and
        returns whatever the service provides. We verify that only
        workspaces from the authenticated user's tenant are returned.
        """
        now = datetime.now(UTC)
        # Only tenant1's workspaces (the mock user's tenant)
        tenant1_ws1 = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=mock_current_user.tenant_id,
            name="Root",
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )
        tenant1_ws2 = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=mock_current_user.tenant_id,
            name="Engineering",
            parent_workspace_id=tenant1_ws1.id,
            is_root=False,
            created_at=now,
            updated_at=now,
        )
        # Service returns ONLY tenant1's workspaces (tenant scoping is enforced by service)
        mock_workspace_service.list_workspaces.return_value = [
            tenant1_ws1,
            tenant1_ws2,
        ]

        response = test_client.get("/iam/workspaces")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["count"] == 2
        # All returned workspaces belong to the user's tenant
        for ws in result["workspaces"]:
            assert ws["tenant_id"] == mock_current_user.tenant_id.value

    def test_list_workspaces_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Test GET /workspaces returns 401 without authentication."""
        response = unauthenticated_test_client.get("/iam/workspaces")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestDeleteWorkspace:
    """Tests for DELETE /iam/workspaces/{id} endpoint."""

    def test_delete_workspace_returns_204(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        child_workspace: Workspace,
    ) -> None:
        """Test DELETE /workspaces/{id} returns 204 on successful deletion."""
        mock_workspace_service.delete_workspace.return_value = True

        response = test_client.delete(
            f"/iam/workspaces/{child_workspace.id.value}",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

    def test_delete_workspace_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test DELETE /workspaces/{id} returns 404 when workspace doesn't exist."""
        mock_workspace_service.delete_workspace.return_value = False
        random_id = WorkspaceId.generate().value

        response = test_client.delete(
            f"/iam/workspaces/{random_id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_delete_workspace_returns_409_for_root(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        root_workspace: Workspace,
    ) -> None:
        """Test DELETE /workspaces/{id} returns 409 when trying to delete root workspace."""
        mock_workspace_service.delete_workspace.side_effect = (
            CannotDeleteRootWorkspaceError("Root workspace cannot be deleted")
        )

        response = test_client.delete(
            f"/iam/workspaces/{root_workspace.id.value}",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "cannot be deleted" in response.json()["detail"].lower()

    def test_delete_workspace_returns_409_for_has_children(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        child_workspace: Workspace,
    ) -> None:
        """Test DELETE /workspaces/{id} returns 409 when workspace has children."""
        mock_workspace_service.delete_workspace.side_effect = WorkspaceHasChildrenError(
            "Cannot delete workspace with children"
        )

        response = test_client.delete(
            f"/iam/workspaces/{child_workspace.id.value}",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "children" in response.json()["detail"].lower()

    def test_delete_workspace_returns_403_for_different_tenant(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test DELETE /workspaces/{id} returns 403 for workspace in different tenant."""
        cross_tenant_workspace_id = WorkspaceId.generate().value
        mock_workspace_service.delete_workspace.side_effect = UnauthorizedError(
            f"Workspace {cross_tenant_workspace_id} belongs to different tenant"
        )

        response = test_client.delete(
            f"/iam/workspaces/{cross_tenant_workspace_id}",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (
            response.json()["detail"]
            == "You do not have permission to perform this action"
        )

    def test_delete_workspace_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Test DELETE /workspaces/{id} returns 401 without authentication."""
        random_id = WorkspaceId.generate().value

        response = unauthenticated_test_client.delete(
            f"/iam/workspaces/{random_id}",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
