"""Integration tests for group-based workspace access inheritance.

Tests the user -> group -> workspace permission chain. When a group is
granted access to a workspace, all group members should inherit that access.

AIHCM-160: Authorization integration tests for group workspace inheritance.
"""

import asyncio

import pytest
import pytest_asyncio

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

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


async def _create_group_with_member(
    async_client: AsyncClient,
    tenant_auth_headers: dict,
    spicedb_client: AuthorizationProvider,
    alice_user_id: str,
    member_user_id: str,
    group_name: str = "test_group",
    member_role: str = "member",
) -> str:
    """Helper: Create a group and add a user as member.

    Returns the group ID.
    """
    # Create group
    group_resp = await async_client.post(
        "/iam/groups",
        headers=tenant_auth_headers,
        json={"name": group_name},
    )
    assert group_resp.status_code == 201
    group_id = group_resp.json()["id"]

    # Wait for alice to have manage permission
    group_resource = format_resource(ResourceType.GROUP, group_id)
    alice_subject = format_subject(ResourceType.USER, alice_user_id)
    await wait_for_permission(
        spicedb_client,
        group_resource,
        Permission.MANAGE,
        alice_subject,
        timeout=5.0,
    )

    # Add member to group
    add_resp = await async_client.post(
        f"/iam/groups/{group_id}/members",
        headers=tenant_auth_headers,
        json={"user_id": member_user_id, "role": member_role},
    )
    assert add_resp.status_code == 201

    # Wait for member permission
    member_subject = format_subject(ResourceType.USER, member_user_id)
    await wait_for_permission(
        spicedb_client,
        group_resource,
        Permission.VIEW,
        member_subject,
        timeout=5.0,
    )

    return group_id


class TestGroupWorkspaceInheritance:
    """Tests for user -> group -> workspace permission chain."""

    @pytest.mark.asyncio
    async def test_group_member_gets_workspace_access_via_group(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Group member should get workspace access when group is added to workspace.

        Tests the chain: workspace#editor@group:{id}#member ->
        group#member_relation@user:{bob_id} => bob has EDIT on workspace.
        """
        # 1. Create workspace (alice is admin)
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="group_inherit_ws",
        )

        # 2. Create group with bob as member
        group_id = await _create_group_with_member(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            member_user_id=bob_user_id,
            group_name="engineering_inherit",
        )

        # 3. Add group to workspace as editor
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

        # 4. Wait for the relationship to propagate
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)

        edit_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )
        assert edit_ready, (
            "Bob should have EDIT permission on workspace via group membership"
        )

        # 5. Verify bob has EDIT but not MANAGE
        has_edit = await spicedb_client.check_permission(
            ws_resource,
            Permission.EDIT,
            bob_subject,
        )
        assert has_edit is True, (
            "Group member should have EDIT permission on workspace via group->editor"
        )

        has_manage = await spicedb_client.check_permission(
            ws_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage is False, (
            "Group member with editor role should NOT have MANAGE permission"
        )

    @pytest.mark.asyncio
    async def test_group_admin_gets_workspace_access_via_group_member_permission(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Group admin should also get workspace access via group member permission.

        Per the SpiceDB schema: group.member = admin + member_relation
        So group admins are also group members and should inherit workspace access.
        """
        # Create workspace
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="group_admin_inherit_ws",
        )

        # Create group with bob as admin
        group_id = await _create_group_with_member(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            member_user_id=bob_user_id,
            group_name="admin_inherit",
            member_role="admin",
        )

        # Wait for bob's manage permission on group (admin)
        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.MANAGE,
            bob_subject,
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

        # Wait for edit permission to propagate via group
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        edit_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )
        assert edit_ready, (
            "Group admin should have EDIT permission on workspace via "
            "group.member = admin + member_relation"
        )

    @pytest.mark.asyncio
    async def test_removing_group_from_workspace_revokes_member_access(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Removing group from workspace should revoke group members' access.

        When the group->workspace relationship is removed, users who had
        access only via group membership should lose that access.
        """
        # Create workspace
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="revoke_group_ws",
        )

        # Create group with bob as member
        group_id = await _create_group_with_member(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            member_user_id=bob_user_id,
            group_name="revoke_group_test",
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

        # Verify bob has EDIT
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        edit_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )
        assert edit_ready, "Bob should have EDIT before group removal"

        # Remove group from workspace
        del_resp = await async_client.delete(
            f"/iam/workspaces/{ws_id}/members/{group_id}?member_type=group",
            headers=tenant_auth_headers,
        )
        assert del_resp.status_code == 204, (
            f"Should be able to remove group from workspace, got {del_resp.status_code}"
        )

        # Allow propagation time
        await asyncio.sleep(0.5)

        # Verify bob no longer has EDIT (may still have VIEW via tenant->view)
        has_edit = await spicedb_client.check_permission(
            ws_resource,
            Permission.EDIT,
            bob_subject,
        )
        assert has_edit is False, (
            "Bob should NOT have EDIT permission after group removed from workspace"
        )

    @pytest.mark.asyncio
    async def test_removing_user_from_group_revokes_workspace_access(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Removing user from group should revoke their workspace access via group.

        When bob is removed from the group, he should lose workspace access
        that was granted via the group membership.
        """
        # Create workspace
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="revoke_user_ws",
        )

        # Create group with bob as member
        group_id = await _create_group_with_member(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            member_user_id=bob_user_id,
            group_name="revoke_user_test",
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

        # Verify bob has EDIT
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        edit_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )
        assert edit_ready, "Bob should have EDIT before group removal"

        # Remove bob from group
        del_resp = await async_client.delete(
            f"/iam/groups/{group_id}/members/{bob_user_id}",
            headers=tenant_auth_headers,
        )
        assert del_resp.status_code == 204, (
            f"Should be able to remove bob from group, got {del_resp.status_code}"
        )

        # Allow propagation time
        await asyncio.sleep(0.5)

        # Verify bob no longer has EDIT via group
        has_edit = await spicedb_client.check_permission(
            ws_resource,
            Permission.EDIT,
            bob_subject,
        )
        assert has_edit is False, (
            "Bob should NOT have EDIT permission after being removed from group"
        )


class TestExplicitTupleListing:
    """Tests verifying workspace member lists show groups, not expanded users."""

    @pytest.mark.asyncio
    async def test_workspace_member_list_shows_groups_not_expanded_users(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Workspace member list should show groups as group entries.

        When a group is added to a workspace, the member list should contain
        the group with member_type='group', not expand it to individual users.
        """
        # Create workspace
        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="tuple_listing_ws",
        )

        # Create group with bob as member
        group_id = await _create_group_with_member(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            member_user_id=bob_user_id,
            group_name="tuple_listing_group",
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

        # List members
        list_resp = await async_client.get(
            f"/iam/workspaces/{ws_id}/members",
            headers=tenant_auth_headers,
        )
        assert list_resp.status_code == 200

        members = list_resp.json()

        # Verify group appears as a group entry
        group_entries = [
            m
            for m in members
            if m.get("member_type") == "group" and m.get("member_id") == group_id
        ]
        assert len(group_entries) == 1, (
            f"Member list should include exactly one group entry for {group_id}, "
            f"got {len(group_entries)}. Members: {members}"
        )
        assert group_entries[0]["role"] == "editor", (
            "Group entry should have editor role"
        )

        # Verify bob does NOT appear as a separate user entry
        # (bob's access is via the group, not a direct grant)
        bob_direct_entries = [
            m
            for m in members
            if m.get("member_type") == "user" and m.get("member_id") == bob_user_id
        ]
        assert len(bob_direct_entries) == 0, (
            f"Bob should NOT appear as a separate user entry since his access is via group. "
            f"Got {bob_direct_entries}"
        )
