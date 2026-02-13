"""Unit tests for Workspace Member HTTP routes.

Tests the presentation layer for workspace member management endpoints
(POST/GET/DELETE /iam/workspaces/{id}/members) following the patterns
established in test_workspaces_routes.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import WorkspaceService
from iam.application.value_objects import CurrentUser, WorkspaceAccessGrant
from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId, UserId, WorkspaceId
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

    # Override dependencies with mocks
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    app.include_router(router)

    return TestClient(app)


class TestAddWorkspaceMember:
    """Tests for POST /iam/workspaces/{workspace_id}/members endpoint."""

    def test_adds_user_member_successfully(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 201 when adding a user member."""
        mock_workspace_service.add_member.return_value = workspace

        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "user",
                "role": "admin",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["member_id"] == "user-alice-123"
        assert result["member_type"] == "user"
        assert result["role"] == "admin"

    def test_adds_group_member_successfully(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 201 when adding a group member."""
        mock_workspace_service.add_member.return_value = workspace

        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "engineering-group",
                "member_type": "group",
                "role": "editor",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["member_id"] == "engineering-group"
        assert result["member_type"] == "group"
        assert result["role"] == "editor"

    def test_adds_member_with_member_role(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 201 with member (viewer) role."""
        mock_workspace_service.add_member.return_value = workspace

        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "bob-user-456",
                "member_type": "user",
                "role": "member",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["role"] == "member"

    def test_returns_400_for_invalid_workspace_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test POST returns 400 when workspace ID is not valid ULID."""
        response = test_client.post(
            "/iam/workspaces/invalid-id/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "user",
                "role": "admin",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid workspace id" in response.json()["detail"].lower()

    def test_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 403 when user lacks MANAGE permission."""
        mock_workspace_service.add_member.side_effect = PermissionError(
            "User lacks manage permission"
        )

        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "user",
                "role": "admin",
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient permissions" in response.json()["detail"].lower()

    def test_returns_403_on_unauthorized_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 403 when workspace belongs to different tenant."""
        mock_workspace_service.add_member.side_effect = UnauthorizedError(
            "Workspace belongs to different tenant"
        )

        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "user",
                "role": "admin",
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "different tenant" in response.json()["detail"].lower()

    def test_returns_400_on_value_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 400 when service raises ValueError (e.g., workspace not found)."""
        mock_workspace_service.add_member.side_effect = ValueError(
            f"Workspace {workspace.id.value} not found"
        )

        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "user",
                "role": "admin",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not found" in response.json()["detail"].lower()

    def test_returns_422_for_invalid_member_type(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 422 for invalid member_type value."""
        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "invalid",
                "role": "admin",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_422_for_invalid_role(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 422 for invalid role value."""
        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "user",
                "role": "superadmin",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_422_for_empty_member_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 422 when member_id is empty."""
        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "",
                "member_type": "user",
                "role": "admin",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_500_on_unexpected_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test POST returns 500 on unexpected exceptions."""
        mock_workspace_service.add_member.side_effect = RuntimeError(
            "DB connection failed"
        )

        response = test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "user",
                "role": "admin",
            },
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to add member" in response.json()["detail"].lower()

    def test_calls_service_with_correct_arguments(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        mock_current_user: CurrentUser,
        workspace: Workspace,
    ) -> None:
        """Test that service is called with properly converted domain objects."""
        from iam.domain.value_objects import MemberType, WorkspaceRole

        mock_workspace_service.add_member.return_value = workspace

        test_client.post(
            f"/iam/workspaces/{workspace.id.value}/members",
            json={
                "member_id": "user-alice-123",
                "member_type": "user",
                "role": "editor",
            },
        )

        mock_workspace_service.add_member.assert_called_once()
        call_kwargs = mock_workspace_service.add_member.call_args.kwargs
        assert call_kwargs["workspace_id"].value == workspace.id.value
        assert call_kwargs["acting_user_id"] == mock_current_user.user_id
        assert call_kwargs["member_id"] == "user-alice-123"
        assert call_kwargs["member_type"] == MemberType.USER
        assert call_kwargs["role"] == WorkspaceRole.EDITOR


class TestListWorkspaceMembers:
    """Tests for GET /iam/workspaces/{workspace_id}/members endpoint."""

    def test_lists_members_successfully(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test GET returns 200 with list of members."""
        mock_workspace_service.list_members.return_value = [
            WorkspaceAccessGrant(
                member_id="alice-user-id", member_type="user", role="admin"
            ),
            WorkspaceAccessGrant(
                member_id="bob-user-id", member_type="user", role="editor"
            ),
            WorkspaceAccessGrant(
                member_id="eng-group-id", member_type="group", role="member"
            ),
        ]

        response = test_client.get(
            f"/iam/workspaces/{workspace.id.value}/members",
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result) == 3
        assert result[0]["member_id"] == "alice-user-id"
        assert result[0]["member_type"] == "user"
        assert result[0]["role"] == "admin"
        assert result[1]["member_id"] == "bob-user-id"
        assert result[1]["member_type"] == "user"
        assert result[1]["role"] == "editor"
        assert result[2]["member_id"] == "eng-group-id"
        assert result[2]["member_type"] == "group"
        assert result[2]["role"] == "member"

    def test_lists_empty_members(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test GET returns 200 with empty list when no members."""
        mock_workspace_service.list_members.return_value = []

        response = test_client.get(
            f"/iam/workspaces/{workspace.id.value}/members",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_returns_400_for_invalid_workspace_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test GET returns 400 when workspace ID is not valid ULID."""
        response = test_client.get(
            "/iam/workspaces/invalid-id/members",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid workspace id" in response.json()["detail"].lower()

    def test_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test GET returns 403 when user lacks VIEW permission."""
        mock_workspace_service.list_members.side_effect = PermissionError(
            "User lacks view permission"
        )

        response = test_client.get(
            f"/iam/workspaces/{workspace.id.value}/members",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient permissions" in response.json()["detail"].lower()

    def test_returns_500_on_unexpected_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test GET returns 500 on unexpected exceptions."""
        mock_workspace_service.list_members.side_effect = RuntimeError(
            "DB connection failed"
        )

        response = test_client.get(
            f"/iam/workspaces/{workspace.id.value}/members",
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to list workspace members" in response.json()["detail"].lower()

    def test_calls_service_with_correct_arguments(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        mock_current_user: CurrentUser,
        workspace: Workspace,
    ) -> None:
        """Test that service is called with correct workspace_id and user_id."""
        mock_workspace_service.list_members.return_value = []

        test_client.get(
            f"/iam/workspaces/{workspace.id.value}/members",
        )

        mock_workspace_service.list_members.assert_called_once()
        call_kwargs = mock_workspace_service.list_members.call_args.kwargs
        assert call_kwargs["workspace_id"].value == workspace.id.value
        assert call_kwargs["user_id"] == mock_current_user.user_id


class TestRemoveWorkspaceMember:
    """Tests for DELETE /iam/workspaces/{workspace_id}/members/{member_id} endpoint."""

    def test_removes_user_member_successfully(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test DELETE returns 204 when removing a user member."""
        mock_workspace_service.remove_member.return_value = workspace

        response = test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

    def test_removes_group_member_successfully(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test DELETE returns 204 when removing a group member."""
        mock_workspace_service.remove_member.return_value = workspace

        response = test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/eng-group-id",
            params={"member_type": "group"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

    def test_returns_400_for_invalid_workspace_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test DELETE returns 400 when workspace ID is not valid ULID."""
        response = test_client.delete(
            "/iam/workspaces/invalid-id/members/alice-user-id",
            params={"member_type": "user"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid workspace id" in response.json()["detail"].lower()

    def test_returns_422_for_missing_member_type(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test DELETE returns 422 when member_type query param is missing."""
        response = test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_422_for_invalid_member_type(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test DELETE returns 422 when member_type is not valid enum."""
        response = test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "invalid"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test DELETE returns 403 when user lacks MANAGE permission."""
        mock_workspace_service.remove_member.side_effect = PermissionError(
            "User lacks manage permission"
        )

        response = test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient permissions" in response.json()["detail"].lower()

    def test_returns_403_on_unauthorized_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test DELETE returns 403 when workspace belongs to different tenant."""
        mock_workspace_service.remove_member.side_effect = UnauthorizedError(
            "Workspace belongs to different tenant"
        )

        response = test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "different tenant" in response.json()["detail"].lower()

    def test_returns_400_on_value_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test DELETE returns 400 when member not found."""
        mock_workspace_service.remove_member.side_effect = ValueError(
            "Member not found in workspace"
        )

        response = test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "member not found" in response.json()["detail"].lower()

    def test_returns_500_on_unexpected_error(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        workspace: Workspace,
    ) -> None:
        """Test DELETE returns 500 on unexpected exceptions."""
        mock_workspace_service.remove_member.side_effect = Exception(
            "DB connection failed"
        )

        response = test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to remove member" in response.json()["detail"].lower()

    def test_calls_service_with_correct_arguments(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        mock_current_user: CurrentUser,
        workspace: Workspace,
    ) -> None:
        """Test that service is called with properly converted domain objects."""
        from iam.domain.value_objects import MemberType

        mock_workspace_service.remove_member.return_value = workspace

        test_client.delete(
            f"/iam/workspaces/{workspace.id.value}/members/alice-user-id",
            params={"member_type": "user"},
        )

        mock_workspace_service.remove_member.assert_called_once()
        call_kwargs = mock_workspace_service.remove_member.call_args.kwargs
        assert call_kwargs["workspace_id"].value == workspace.id.value
        assert call_kwargs["acting_user_id"] == mock_current_user.user_id
        assert call_kwargs["member_id"] == "alice-user-id"
        assert call_kwargs["member_type"] == MemberType.USER
