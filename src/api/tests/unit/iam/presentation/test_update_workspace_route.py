"""Unit tests for PATCH /iam/workspaces/{workspace_id} route.

Tests the presentation layer for updating workspace metadata (rename).
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
from iam.ports.exceptions import DuplicateWorkspaceNameError, UnauthorizedError


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
def workspace(mock_current_user: CurrentUser) -> Workspace:
    """Create a workspace for testing."""
    now = datetime.now(UTC)
    return Workspace(
        id=WorkspaceId.generate(),
        tenant_id=mock_current_user.tenant_id,
        name="Engineering",
        parent_workspace_id=WorkspaceId.generate(),
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

    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    app.include_router(router)

    return TestClient(app)


class TestUpdateWorkspace:
    """Tests for PATCH /iam/workspaces/{workspace_id} endpoint."""

    def test_updates_workspace_name_successfully(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 200 when updating workspace name."""
        # Create a copy with updated name to return from service
        updated = Workspace(
            id=workspace.id,
            tenant_id=workspace.tenant_id,
            name="Platform Engineering",
            parent_workspace_id=workspace.parent_workspace_id,
            is_root=False,
            created_at=workspace.created_at,
            updated_at=datetime.now(UTC),
        )
        mock_workspace_service.update_workspace.return_value = updated

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": "Platform Engineering"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["id"] == workspace.id.value
        assert result["name"] == "Platform Engineering"

    def test_returns_400_for_invalid_workspace_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test PATCH returns 400 when workspace ID is not valid ULID."""
        response = test_client.patch(
            "/iam/workspaces/invalid-id",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid workspace id" in response.json()["detail"].lower()

    def test_returns_422_for_empty_name(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 422 when name is empty."""
        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": ""},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_returns_422_for_name_too_long(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 422 when name exceeds 512 characters."""
        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": "x" * 513},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 403 when user lacks MANAGE permission."""
        mock_workspace_service.update_workspace.side_effect = UnauthorizedError(
            "User lacks manage permission"
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "lacks manage permission" in response.json()["detail"].lower()

    def test_returns_409_for_duplicate_name(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 409 when name already exists in tenant."""
        mock_workspace_service.update_workspace.side_effect = (
            DuplicateWorkspaceNameError(
                "Workspace 'Marketing' already exists in tenant"
            )
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": "Marketing"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"].lower()

    def test_returns_400_on_value_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 404 when workspace not found."""
        mock_workspace_service.update_workspace.side_effect = ValueError(
            f"Workspace {workspace.id.value} not found"
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_returns_403_on_unauthorized_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 403 when workspace belongs to different tenant."""
        mock_workspace_service.update_workspace.side_effect = UnauthorizedError(
            "Workspace belongs to different tenant"
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "different tenant" in response.json()["detail"].lower()

    def test_returns_500_on_unexpected_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 500 on unexpected exceptions."""
        mock_workspace_service.update_workspace.side_effect = Exception(
            "DB connection failed"
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to update workspace" in response.json()["detail"].lower()

    def test_calls_service_with_correct_arguments(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        mock_current_user: CurrentUser,
        workspace: Workspace,
    ) -> None:
        """Test that service is called with properly converted domain objects."""
        mock_workspace_service.update_workspace.return_value = workspace

        test_client.patch(
            f"/iam/workspaces/{workspace.id.value}",
            json={"name": "New Name"},
        )

        mock_workspace_service.update_workspace.assert_called_once()
        call_kwargs = mock_workspace_service.update_workspace.call_args.kwargs
        assert call_kwargs["workspace_id"].value == workspace.id.value
        assert call_kwargs["user_id"] == mock_current_user.user_id
        assert call_kwargs["name"] == "New Name"
