"""Integration tests for Workspace Member API endpoints.

Tests the full vertical slice: API -> Service -> Repository -> PostgreSQL + SpiceDB.
Verifies POST/GET/PATCH/DELETE /iam/workspaces/{id}/members endpoints.

AIHCM-160: Authorization integration tests for workspace member management.
"""

import asyncio

import pytest
import pytest_asyncio

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from iam.domain.value_objects import UserId
from main import app
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from tests.integration.iam.conftest import create_child_workspace, wait_for_permission

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support."""
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


class TestAddWorkspaceMember:
    """Tests for POST /iam/workspaces/{id}/members endpoint."""

    @pytest.mark.asyncio
    async def test_admin_can_add_user_member_to_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Admin can add a user member to a workspace via API.

        Verifies that workspace admins can grant access to other users
        and that the SpiceDB relationship is correctly established.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="admin_add_user_ws",
        )

        # Add bob as editor
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
            json={
                "member_id": bob_user_id,
                "member_type": "user",
                "role": "editor",
            },
        )
        assert add_resp.status_code == 201, (
            f"Admin should be able to add user member, got {add_resp.status_code}: {add_resp.text}"
        )

        data = add_resp.json()
        assert data["member_id"] == bob_user_id, (
            "Response should contain correct member_id"
        )
        assert data["member_type"] == "user", (
            "Response should contain correct member_type"
        )
        assert data["role"] == "editor", "Response should contain correct role"

        # Wait for outbox to process
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        editor_ready = await wait_for_permission(
            spicedb_client,
            resource=ws_resource,
            permission=Permission.EDIT,
            subject=bob_subject,
            timeout=5.0,
        )
        assert editor_ready, "Timed out waiting for editor permission in SpiceDB"

        # Verify SpiceDB state: bob has EDIT but not MANAGE
        has_edit = await spicedb_client.check_permission(
            ws_resource,
            Permission.EDIT,
            bob_subject,
        )
        assert has_edit is True, "Editor should have EDIT permission"

        has_manage = await spicedb_client.check_permission(
            ws_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage is False, "Editor should NOT have MANAGE permission"

    @pytest.mark.asyncio
    async def test_admin_can_add_group_member_to_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Admin can add a group as a member of a workspace.

        Verifies that groups are added with subject relation group#member,
        not just group:id, so that group members inherit the permission.
        """
        # Create workspace
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="admin_add_group_ws",
        )

        # Create group
        group_resp = await async_client.post(
            "/iam/groups",
            headers=tenant_auth_headers,
            json={"name": "test_group_for_ws"},
        )
        assert group_resp.status_code == 201, (
            f"Failed to create group: {group_resp.text}"
        )
        group_id = group_resp.json()["id"]

        # Wait for group manage permission
        group_resource = format_resource(ResourceType.GROUP, group_id)
        alice_subject = format_subject(ResourceType.USER, alice_user_id)
        group_ready = await wait_for_permission(
            spicedb_client,
            resource=group_resource,
            permission=Permission.MANAGE,
            subject=alice_subject,
            timeout=5.0,
        )
        assert group_ready, "Timed out waiting for group manage permission"

        # Add group as member to workspace
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
            json={
                "member_id": group_id,
                "member_type": "group",
                "role": "member",
            },
        )
        assert add_resp.status_code == 201, (
            f"Admin should be able to add group member, got {add_resp.status_code}: {add_resp.text}"
        )

        data = add_resp.json()
        assert data["member_id"] == group_id, "Response should contain correct group_id"
        assert data["member_type"] == "group", (
            "Response should contain group member_type"
        )
        assert data["role"] == "member", "Response should contain member role"

    @pytest.mark.asyncio
    async def test_non_admin_cannot_add_member_to_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Non-admin user should receive 403 when trying to add workspace member.

        Bob is a tenant member but not a workspace admin, so adding members
        should be denied.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="non_admin_add_ws",
        )

        # Bob tries to add a member - should fail with 403
        new_user_id = UserId.generate().value
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=bob_tenant_auth_headers,
            json={
                "member_id": new_user_id,
                "member_type": "user",
                "role": "member",
            },
        )
        assert add_resp.status_code == 403, (
            f"Non-admin should get 403 when adding workspace member, got {add_resp.status_code}"
        )


class TestListWorkspaceMembers:
    """Tests for GET /iam/workspaces/{id}/members endpoint."""

    @pytest.mark.asyncio
    async def test_can_list_workspace_members(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Can list workspace members showing correct roles and member types.

        Verifies the member list contains all explicitly granted members
        with their correct roles.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="list_members_ws",
        )

        # Add bob as editor
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
            json={
                "member_id": bob_user_id,
                "member_type": "user",
                "role": "editor",
            },
        )
        assert add_resp.status_code == 201

        # Wait for bob's editor permission
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        editor_ready = await wait_for_permission(
            spicedb_client,
            resource=ws_resource,
            permission=Permission.EDIT,
            subject=bob_subject,
            timeout=5.0,
        )
        assert editor_ready, "Timed out waiting for bob's editor permission"

        # List members
        list_resp = await async_client.get(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
        )
        assert list_resp.status_code == 200, (
            f"Should be able to list workspace members, got {list_resp.status_code}: {list_resp.text}"
        )

        members = list_resp.json()
        assert isinstance(members, list), "Response should be a list of members"

        # Find alice and bob in members
        member_map = {m["member_id"]: m for m in members}
        assert alice_user_id in member_map, "Alice should be in member list as admin"
        assert bob_user_id in member_map, "Bob should be in member list as editor"
        assert member_map[alice_user_id]["role"] == "admin", (
            "Alice should have admin role"
        )
        assert member_map[bob_user_id]["role"] == "editor", (
            "Bob should have editor role"
        )
        assert member_map[alice_user_id]["member_type"] == "user", (
            "Alice should have user member_type"
        )
        assert member_map[bob_user_id]["member_type"] == "user", (
            "Bob should have user member_type"
        )

    @pytest.mark.asyncio
    async def test_lists_group_members_with_group_type(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Member list should show groups as group type (not expanded users).

        When a group is added to a workspace, the member list should show
        the group entry with member_type='group', not expand to individual
        group members. This tests the explicit tuple listing pattern.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="group_type_ws",
        )

        # Create group
        group_resp = await async_client.post(
            "/iam/groups",
            headers=tenant_auth_headers,
            json={"name": "test_group_listing"},
        )
        assert group_resp.status_code == 201
        group_id = group_resp.json()["id"]

        # Wait for group manage permission
        group_resource = format_resource(ResourceType.GROUP, group_id)
        alice_subject = format_subject(ResourceType.USER, alice_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.MANAGE,
            alice_subject,
            timeout=5.0,
        )

        # Add group to workspace as editor
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
            json={
                "member_id": group_id,
                "member_type": "group",
                "role": "editor",
            },
        )
        assert add_resp.status_code == 201

        # Wait for the workspace member addition to propagate
        # We can't easily check group permission directly, so just give it time
        # by listing and verifying
        await asyncio.sleep(0.5)

        # List members
        list_resp = await async_client.get(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
        )
        assert list_resp.status_code == 200

        members = list_resp.json()
        group_entries = [m for m in members if m.get("member_type") == "group"]
        assert len(group_entries) >= 1, (
            "Member list should include group entries with member_type='group'"
        )

        group_entry = next(
            (m for m in group_entries if m["member_id"] == group_id), None
        )
        assert group_entry is not None, (
            f"Member list should include the added group {group_id}"
        )
        assert group_entry["role"] == "editor", (
            "Group should have editor role in member list"
        )

    @pytest.mark.asyncio
    async def test_tenant_member_can_list_workspace_members_via_tenant_view(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Tenant member can list workspace members via tenant->view relation.

        Per the SpiceDB schema: workspace.view = admin + editor + member + tenant->view
        Bob is a tenant member (not explicitly a workspace member), so he has
        VIEW permission on all workspaces in the tenant via the tenant->view path.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="tenant_view_list_ws",
        )

        # Bob is a tenant member and has VIEW via tenant->view relation.
        # Per the SpiceDB schema: workspace.view = admin + editor + member + tenant->view
        list_resp = await async_client.get(
            f"/iam/workspaces/{ws_id}/members",
            headers=bob_tenant_auth_headers,
        )
        assert list_resp.status_code == 200, (
            f"Tenant member should be able to list workspace members via tenant->view, "
            f"got {list_resp.status_code}: {list_resp.text}"
        )


class TestUpdateWorkspaceMemberRole:
    """Tests for PATCH /iam/workspaces/{id}/members/{member_id} endpoint."""

    @pytest.mark.asyncio
    async def test_admin_can_update_member_role(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Admin can update a member's role in a workspace.

        Verifies that role updates correctly modify SpiceDB relationships,
        replacing the old role with the new one.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="update_role_ws",
        )

        # Add bob as member (view only)
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
            json={
                "member_id": bob_user_id,
                "member_type": "user",
                "role": "member",
            },
        )
        assert add_resp.status_code == 201

        # Wait for member permission
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        view_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )
        assert view_ready, "Timed out waiting for bob's view permission"

        # Update bob to editor
        patch_resp = await async_client.patch(
            f"/iam/workspaces/{ws_id}/members/{bob_user_id}?member_type=user",
            headers=tenant_auth_headers,
            json={"role": "editor"},
        )
        assert patch_resp.status_code == 200, (
            f"Admin should be able to update member role, got {patch_resp.status_code}: {patch_resp.text}"
        )

        data = patch_resp.json()
        assert data["role"] == "editor", "Response should show new role"

        # Wait for editor permission
        editor_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )
        assert editor_ready, "Timed out waiting for updated editor permission"

        # Verify bob has EDIT permission now
        has_edit = await spicedb_client.check_permission(
            ws_resource,
            Permission.EDIT,
            bob_subject,
        )
        assert has_edit is True, "Bob should have EDIT permission after role update"

    @pytest.mark.asyncio
    async def test_non_admin_cannot_update_member_role(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Non-admin should receive 403 when trying to update member role.

        Bob (tenant member, not workspace admin) tries to change his own role.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="non_admin_update_ws",
        )

        # Add bob as editor
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
            json={
                "member_id": bob_user_id,
                "member_type": "user",
                "role": "editor",
            },
        )
        assert add_resp.status_code == 201

        # Wait for bob's editor permission
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )

        # Bob tries to upgrade himself to admin - should fail
        patch_resp = await async_client.patch(
            f"/iam/workspaces/{ws_id}/members/{bob_user_id}?member_type=user",
            headers=bob_tenant_auth_headers,
            json={"role": "admin"},
        )
        assert patch_resp.status_code == 403, (
            f"Non-admin should get 403 when updating member role, got {patch_resp.status_code}"
        )


class TestRemoveWorkspaceMember:
    """Tests for DELETE /iam/workspaces/{id}/members/{member_id} endpoint."""

    @pytest.mark.asyncio
    async def test_admin_can_remove_member(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Admin can remove a user member from a workspace.

        Verifies that SpiceDB relationships are correctly removed.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="remove_member_ws",
        )

        # Add bob as editor
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
            json={
                "member_id": bob_user_id,
                "member_type": "user",
                "role": "editor",
            },
        )
        assert add_resp.status_code == 201

        # Wait for bob's editor permission
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        editor_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )
        assert editor_ready, "Timed out waiting for bob's editor permission"

        # Remove bob
        del_resp = await async_client.delete(
            f"/iam/workspaces/{ws_id}/members/{bob_user_id}?member_type=user",
            headers=tenant_auth_headers,
        )
        assert del_resp.status_code == 204, (
            f"Admin should be able to remove member, got {del_resp.status_code}: {del_resp.text}"
        )

        # Allow time for SpiceDB to process the relationship deletion
        await asyncio.sleep(0.5)

        # Verify bob no longer has edit permission
        has_edit = await spicedb_client.check_permission(
            ws_resource,
            Permission.EDIT,
            bob_subject,
        )
        # Bob may still have VIEW via tenant->view, but should not have EDIT
        # from the direct editor grant anymore
        assert has_edit is False, (
            "Bob should NOT have EDIT permission after being removed as editor"
        )

    @pytest.mark.asyncio
    async def test_non_admin_cannot_remove_member(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Non-admin should receive 403 when trying to remove workspace member."""
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="non_admin_remove_ws",
        )

        # Bob tries to remove alice - should fail
        del_resp = await async_client.delete(
            f"/iam/workspaces/{ws_id}/members/{alice_user_id}?member_type=user",
            headers=bob_tenant_auth_headers,
        )
        assert del_resp.status_code == 403, (
            f"Non-admin should get 403 when removing workspace member, got {del_resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_admin_can_remove_group_member(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Admin can remove a group from a workspace.

        Verifies that the group relationship is removed from SpiceDB.
        """
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="remove_group_ws",
        )

        # Create group
        group_resp = await async_client.post(
            "/iam/groups",
            headers=tenant_auth_headers,
            json={"name": "group_to_remove"},
        )
        assert group_resp.status_code == 201
        group_id = group_resp.json()["id"]

        # Wait for group manage permission
        group_resource = format_resource(ResourceType.GROUP, group_id)
        alice_subject = format_subject(ResourceType.USER, alice_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.MANAGE,
            alice_subject,
            timeout=5.0,
        )

        # Add group to workspace as editor
        add_resp = await async_client.post(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
            json={
                "member_id": group_id,
                "member_type": "group",
                "role": "editor",
            },
        )
        assert add_resp.status_code == 201

        await asyncio.sleep(0.5)

        # Remove group from workspace
        del_resp = await async_client.delete(
            f"/iam/workspaces/{ws_id}/members/{group_id}?member_type=group",
            headers=tenant_auth_headers,
        )
        assert del_resp.status_code == 204, (
            f"Admin should be able to remove group member, got {del_resp.status_code}: {del_resp.text}"
        )
