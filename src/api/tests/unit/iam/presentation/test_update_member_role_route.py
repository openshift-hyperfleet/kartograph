"""Unit tests for PATCH /iam/workspaces/{workspace_id}/members/{member_id} route.

Tests the presentation layer for updating a workspace member's role.
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
from iam.domain.value_objects import (
    MemberType,
    TenantId,
    UserId,
    WorkspaceId,
    WorkspaceRole,
)
from iam.ports.exceptions import UnauthorizedError


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
    """Create a workspace for testing member operations."""
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


class TestUpdateWorkspaceMemberRole:
    """Tests for PATCH /iam/workspaces/{workspace_id}/members/{member_id} endpoint."""

    def test_updates_user_role_successfully(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 200 when updating a user member's role."""
        mock_workspace_service.update_member_role.return_value = workspace

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
            json={"role": "editor"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["member_id"] == "alice-user-id"
        assert result["member_type"] == "user"
        assert result["role"] == "editor"

    def test_updates_group_role_successfully(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 200 when updating a group member's role."""
        mock_workspace_service.update_member_role.return_value = workspace

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/eng-group-id",
            params={"member_type": "group"},
            json={"role": "admin"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["member_id"] == "eng-group-id"
        assert result["member_type"] == "group"
        assert result["role"] == "admin"

    def test_returns_400_for_invalid_workspace_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test PATCH returns 400 when workspace ID is not valid ULID."""
        response = test_client.patch(
            "/iam/workspaces/invalid-id/members/alice-user-id",
            params={"member_type": "user"},
            json={"role": "editor"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid workspace id" in response.json()["detail"].lower()

    def test_returns_422_for_missing_member_type(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 422 when member_type query param is missing."""
        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            json={"role": "editor"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_422_for_invalid_member_type(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 422 when member_type is not valid enum."""
        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "invalid"},
            json={"role": "editor"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_422_for_invalid_role(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 422 for invalid role value."""
        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
            json={"role": "superadmin"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 403 when user lacks MANAGE permission."""
        mock_workspace_service.update_member_role.side_effect = PermissionError(
            "User lacks manage permission"
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
            json={"role": "editor"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient permissions" in response.json()["detail"].lower()

    def test_returns_403_on_unauthorized_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 403 when workspace belongs to different tenant."""
        mock_workspace_service.update_member_role.side_effect = UnauthorizedError(
            "Workspace belongs to different tenant"
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
            json={"role": "editor"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "different tenant" in response.json()["detail"].lower()

    def test_returns_400_on_value_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 400 when member not found or role unchanged."""
        mock_workspace_service.update_member_role.side_effect = ValueError(
            "Member already has role editor"
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
            json={"role": "editor"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already has role" in response.json()["detail"].lower()

    def test_returns_500_on_unexpected_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test PATCH returns 500 on unexpected exceptions."""
        mock_workspace_service.update_member_role.side_effect = Exception(
            "DB connection failed"
        )

        response = test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
            json={"role": "editor"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to update member role" in response.json()["detail"].lower()

    def test_calls_service_with_correct_arguments(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        mock_current_user: CurrentUser,
        workspace: Workspace,
    ) -> None:
        """Test that service is called with properly converted domain objects."""
        mock_workspace_service.update_member_role.return_value = workspace

        test_client.patch(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
            json={"role": "editor"},
        )

        mock_workspace_service.update_member_role.assert_called_once()
        call_kwargs = mock_workspace_service.update_member_role.call_args.kwargs
        assert call_kwargs["workspace_id"].value == workspace.id.value
        assert call_kwargs["acting_user_id"] == mock_current_user.user_id
        assert call_kwargs["member_id"] == "alice-user-id"
        assert call_kwargs["member_type"] == MemberType.USER
        assert call_kwargs["new_role"] == WorkspaceRole.EDITOR
