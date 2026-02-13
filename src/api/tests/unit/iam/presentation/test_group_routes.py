"""Unit tests for Group HTTP routes.

Tests the presentation layer for group endpoints including
member management, rename, and VIEW-filtered list.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import GroupService
from iam.application.value_objects import CurrentUser
from iam.domain.aggregates import Group
from iam.domain.value_objects import (
    GroupId,
    GroupMember,
    GroupRole,
    TenantId,
    UserId,
)
from iam.ports.exceptions import DuplicateGroupNameError


@pytest.fixture
def mock_group_service() -> AsyncMock:
    """Mock GroupService for testing."""
    return AsyncMock(spec=GroupService)


@pytest.fixture
def mock_current_user() -> CurrentUser:
    """Mock CurrentUser for authentication."""
    return CurrentUser(
        user_id=UserId(value="test-user-123"),
        username="testuser",
        tenant_id=TenantId.generate(),
    )


@pytest.fixture
def test_client(
    mock_group_service: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies.group import get_group_service
    from iam.dependencies.user import get_current_user
    from iam.presentation import router

    app = FastAPI()

    app.dependency_overrides[get_group_service] = lambda: mock_group_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    app.include_router(router)

    return TestClient(app)


class TestListGroupsWithViewFiltering:
    """Tests for GET /iam/groups with VIEW permission filtering."""

    def test_list_groups_passes_user_id_to_service(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Test that list_groups passes user_id to the service."""
        mock_group_service.list_groups.return_value = []

        response = test_client.get("/iam/groups")

        assert response.status_code == status.HTTP_200_OK
        mock_group_service.list_groups.assert_called_once_with(
            user_id=mock_current_user.user_id
        )

    def test_list_groups_returns_filtered_groups(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Test that list_groups returns VIEW-filtered groups."""
        tenant_id = mock_current_user.tenant_id
        group1 = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Engineering",
            members=[],
        )
        group2 = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Marketing",
            members=[],
        )
        mock_group_service.list_groups.return_value = [group1, group2]

        response = test_client.get("/iam/groups")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result) == 2
        assert result[0]["name"] == "Engineering"
        assert result[1]["name"] == "Marketing"


class TestGroupMemberRoutes:
    """Tests for group member management routes."""

    def test_add_member_returns_201(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Test POST /groups/{id}/members returns 201."""
        group_id = GroupId.generate()
        new_user_id = UserId.generate()
        tenant_id = mock_current_user.tenant_id
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering",
            members=[
                GroupMember(user_id=new_user_id, role=GroupRole.MEMBER),
            ],
        )
        mock_group_service.add_member.return_value = group

        response = test_client.post(
            f"/iam/groups/{group_id.value}/members",
            json={
                "user_id": new_user_id.value,
                "role": "member",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["user_id"] == new_user_id.value
        assert result["role"] == "member"

    def test_add_member_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test POST /groups/{id}/members returns 403 when lacking permission."""
        group_id = GroupId.generate()
        mock_group_service.add_member.side_effect = PermissionError(
            "User lacks manage permission"
        )

        response = test_client.post(
            f"/iam/groups/{group_id.value}/members",
            json={
                "user_id": "some-user-id",
                "role": "member",
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_add_member_returns_400_on_value_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test POST /groups/{id}/members returns 400 on ValueError."""
        group_id = GroupId.generate()
        mock_group_service.add_member.side_effect = ValueError("User already a member")

        response = test_client.post(
            f"/iam/groups/{group_id.value}/members",
            json={
                "user_id": "some-user-id",
                "role": "member",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_add_member_returns_400_for_invalid_group_id(
        self,
        test_client: TestClient,
    ) -> None:
        """Test POST /groups/{id}/members returns 400 for invalid group ID."""
        response = test_client.post(
            "/iam/groups/invalid-id/members",
            json={
                "user_id": "some-user-id",
                "role": "member",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_add_member_returns_422_for_invalid_role(
        self,
        test_client: TestClient,
    ) -> None:
        """Test POST /groups/{id}/members returns 422 for invalid role."""
        group_id = GroupId.generate()
        response = test_client.post(
            f"/iam/groups/{group_id.value}/members",
            json={
                "user_id": "some-user-id",
                "role": "superadmin",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_list_members_returns_200(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test GET /groups/{id}/members returns 200 with members."""
        from iam.application.value_objects import GroupAccessGrant

        group_id = GroupId.generate()
        mock_group_service.list_members.return_value = [
            GroupAccessGrant(
                user_id="admin-user-1",
                role=GroupRole.ADMIN,
            ),
            GroupAccessGrant(
                user_id="member-user-1",
                role=GroupRole.MEMBER,
            ),
        ]

        response = test_client.get(
            f"/iam/groups/{group_id.value}/members",
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result) == 2
        assert result[0]["user_id"] == "admin-user-1"
        assert result[0]["role"] == "admin"

    def test_list_members_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test GET /groups/{id}/members returns 403 without VIEW."""
        group_id = GroupId.generate()
        mock_group_service.list_members.side_effect = PermissionError(
            "User lacks view permission"
        )

        response = test_client.get(
            f"/iam/groups/{group_id.value}/members",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_member_role_returns_200(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Test PATCH /groups/{id}/members/{user_id} returns 200."""
        group_id = GroupId.generate()
        member_user_id = UserId.generate()
        group = Group(
            id=group_id,
            tenant_id=mock_current_user.tenant_id,
            name="Engineering",
            members=[
                GroupMember(user_id=member_user_id, role=GroupRole.ADMIN),
            ],
        )
        mock_group_service.update_member_role.return_value = group

        response = test_client.patch(
            f"/iam/groups/{group_id.value}/members/{member_user_id.value}",
            json={"role": "admin"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["user_id"] == member_user_id.value
        assert result["role"] == "admin"

    def test_update_member_role_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test PATCH /groups/{id}/members/{user_id} returns 403."""
        group_id = GroupId.generate()
        mock_group_service.update_member_role.side_effect = PermissionError(
            "User lacks manage permission"
        )

        response = test_client.patch(
            f"/iam/groups/{group_id.value}/members/some-user",
            json={"role": "admin"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_remove_member_returns_204(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Test DELETE /groups/{id}/members/{user_id} returns 204."""
        group_id = GroupId.generate()
        member_user_id = UserId.generate()
        group = Group(
            id=group_id,
            tenant_id=mock_current_user.tenant_id,
            name="Engineering",
        )
        mock_group_service.remove_member.return_value = group

        response = test_client.delete(
            f"/iam/groups/{group_id.value}/members/{member_user_id.value}",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

    def test_remove_member_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test DELETE /groups/{id}/members/{user_id} returns 403."""
        group_id = GroupId.generate()
        mock_group_service.remove_member.side_effect = PermissionError(
            "User lacks manage permission"
        )

        response = test_client.delete(
            f"/iam/groups/{group_id.value}/members/some-user",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_remove_member_returns_400_on_value_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test DELETE /groups/{id}/members/{user_id} returns 400."""
        group_id = GroupId.generate()
        mock_group_service.remove_member.side_effect = ValueError("User not a member")

        response = test_client.delete(
            f"/iam/groups/{group_id.value}/members/some-user",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUpdateGroupRoute:
    """Tests for PATCH /iam/groups/{group_id} endpoint."""

    def test_update_group_returns_200(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Test PATCH /groups/{id} returns 200 with updated group."""
        group_id = GroupId.generate()
        group = Group(
            id=group_id,
            tenant_id=mock_current_user.tenant_id,
            name="Platform Engineering",
            members=[],
        )
        mock_group_service.update_group.return_value = group

        response = test_client.patch(
            f"/iam/groups/{group_id.value}",
            json={"name": "Platform Engineering"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["name"] == "Platform Engineering"

    def test_update_group_returns_403_on_permission_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test PATCH /groups/{id} returns 403 on PermissionError."""
        group_id = GroupId.generate()
        mock_group_service.update_group.side_effect = PermissionError(
            "User lacks manage permission"
        )

        response = test_client.patch(
            f"/iam/groups/{group_id.value}",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_group_returns_409_on_duplicate_name(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test PATCH /groups/{id} returns 409 on DuplicateGroupNameError."""
        group_id = GroupId.generate()
        mock_group_service.update_group.side_effect = DuplicateGroupNameError(
            "Group 'Engineering' already exists"
        )

        response = test_client.patch(
            f"/iam/groups/{group_id.value}",
            json={"name": "Engineering"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_update_group_returns_400_on_value_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test PATCH /groups/{id} returns 400 on ValueError."""
        group_id = GroupId.generate()
        mock_group_service.update_group.side_effect = ValueError("Group not found")

        response = test_client.patch(
            f"/iam/groups/{group_id.value}",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_group_returns_400_for_invalid_group_id(
        self,
        test_client: TestClient,
    ) -> None:
        """Test PATCH /groups/{id} returns 400 for invalid group ID."""
        response = test_client.patch(
            "/iam/groups/invalid-id",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_group_returns_422_for_empty_name(
        self,
        test_client: TestClient,
    ) -> None:
        """Test PATCH /groups/{id} returns 422 for empty name."""
        group_id = GroupId.generate()
        response = test_client.patch(
            f"/iam/groups/{group_id.value}",
            json={"name": ""},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestWorkspaceMemberResponseEnums:
    """Tests verifying WorkspaceMemberResponse uses enums (not plain strings)."""

    def test_workspace_member_response_uses_enum_types(self) -> None:
        """WorkspaceMemberResponse should use MemberTypeEnum and WorkspaceRoleEnum."""
        from iam.presentation.workspaces.models import WorkspaceMemberResponse

        schema = WorkspaceMemberResponse.model_json_schema()

        # member_type should reference an enum
        member_type_ref = schema["properties"]["member_type"]
        assert (
            "$ref" in member_type_ref
            or "enum" in member_type_ref
            or "allOf" in member_type_ref
        )

        # role should reference an enum
        role_ref = schema["properties"]["role"]
        assert "$ref" in role_ref or "enum" in role_ref or "allOf" in role_ref


class TestRemoveWorkspaceMemberErrorCodes:
    """Tests for remove_workspace_member error code handling."""

    def test_workspace_not_found_returns_404(
        self,
    ) -> None:
        """When service raises ValueError mentioning 'Workspace' and 'not found',
        route should return 404 not 400."""
        from iam.application.services import WorkspaceService
        from iam.dependencies.user import get_current_user
        from iam.dependencies.workspace import get_workspace_service
        from iam.presentation import router

        mock_ws_service = AsyncMock(spec=WorkspaceService)
        mock_user = CurrentUser(
            user_id=UserId(value="test-user-123"),
            username="testuser",
            tenant_id=TenantId.generate(),
        )

        app = FastAPI()
        app.dependency_overrides[get_workspace_service] = lambda: mock_ws_service
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.include_router(router)
        client = TestClient(app)

        from iam.domain.value_objects import WorkspaceId

        ws_id = WorkspaceId.generate()
        mock_ws_service.remove_member.side_effect = ValueError(
            f"Workspace {ws_id.value} not found"
        )

        response = client.delete(
            f"/iam/workspaces/{ws_id.value}/members/alice-user-id",
            params={"member_type": "user"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_member_not_found_returns_400(
        self,
    ) -> None:
        """When service raises ValueError about member not found, return 400."""
        from iam.application.services import WorkspaceService
        from iam.dependencies.user import get_current_user
        from iam.dependencies.workspace import get_workspace_service
        from iam.presentation import router

        mock_ws_service = AsyncMock(spec=WorkspaceService)
        mock_user = CurrentUser(
            user_id=UserId(value="test-user-123"),
            username="testuser",
            tenant_id=TenantId.generate(),
        )

        app = FastAPI()
        app.dependency_overrides[get_workspace_service] = lambda: mock_ws_service
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.include_router(router)
        client = TestClient(app)

        from iam.domain.value_objects import WorkspaceId

        ws_id = WorkspaceId.generate()
        mock_ws_service.remove_member.side_effect = ValueError(
            "user alice is not a member of this workspace"
        )

        response = client.delete(
            f"/iam/workspaces/{ws_id.value}/members/alice-user-id",
            params={"member_type": "user"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
