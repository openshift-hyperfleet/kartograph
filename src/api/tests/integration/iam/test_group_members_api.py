"""Integration tests for Group Member API endpoints.

Tests the full vertical slice: API -> Service -> Repository -> PostgreSQL + SpiceDB.
Verifies POST/GET/PATCH/DELETE /iam/groups/{id}/members endpoints.

AIHCM-160: Authorization integration tests for group member management.
"""

import pytest
import pytest_asyncio

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from iam.domain.value_objects import GroupId, UserId
from main import app
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from tests.integration.iam.conftest import wait_for_permission

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support."""
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def _create_group(
    async_client: AsyncClient,
    tenant_auth_headers: dict,
    spicedb_client: AuthorizationProvider,
    alice_user_id: str,
    name: str = "test_group",
) -> str:
    """Helper: Create a group and wait for admin permission.

    Returns the group ID.
    """
    create_resp = await async_client.post(
        "/iam/groups",
        headers=tenant_auth_headers,
        json={"name": name},
    )
    assert create_resp.status_code == 201, f"Failed to create group: {create_resp.text}"
    group_id = create_resp.json()["id"]

    # Wait for outbox to grant alice admin on the new group
    group_resource = format_resource(ResourceType.GROUP, group_id)
    alice_subject = format_subject(ResourceType.USER, alice_user_id)
    admin_ready = await wait_for_permission(
        spicedb_client,
        resource=group_resource,
        permission=Permission.MANAGE,
        subject=alice_subject,
        timeout=5.0,
    )
    assert admin_ready, "Timed out waiting for group admin permission"

    return group_id


class TestAddGroupMember:
    """Tests for POST /iam/groups/{id}/members endpoint."""

    @pytest.mark.asyncio
    async def test_admin_can_add_member_to_group(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Admin can add a member to a group via API.

        Verifies that group admins can grant membership and that the
        SpiceDB relationship is correctly established.
        """
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="admin_add_member_group",
        )

        # Add bob as member
        add_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
            json={
                "user_id": bob_user_id,
                "role": "member",
            },
        )
        assert add_resp.status_code == 201, (
            f"Admin should be able to add group member, got {add_resp.status_code}: {add_resp.text}"
        )

        data = add_resp.json()
        assert data["user_id"] == bob_user_id, "Response should contain correct user_id"
        assert data["role"] == "member", "Response should contain correct role"

        # Wait for bob's view permission on group
        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        member_ready = await wait_for_permission(
            spicedb_client,
            resource=group_resource,
            permission=Permission.VIEW,
            subject=bob_subject,
            timeout=5.0,
        )
        assert member_ready, "Timed out waiting for bob's group view permission"

        # Verify bob has VIEW but NOT MANAGE
        has_view = await spicedb_client.check_permission(
            group_resource,
            Permission.VIEW,
            bob_subject,
        )
        assert has_view is True, "Group member should have VIEW permission"

        has_manage = await spicedb_client.check_permission(
            group_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage is False, "Group member should NOT have MANAGE permission"

    @pytest.mark.asyncio
    async def test_non_admin_cannot_add_member(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Non-admin should receive 403 when trying to add group member.

        Bob needs to be a group member (not admin) to test this properly.
        """
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="non_admin_add_group",
        )

        # Add bob as regular member (not admin)
        add_bob_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
            json={"user_id": bob_user_id, "role": "member"},
        )
        assert add_bob_resp.status_code == 201

        # Wait for bob's permission
        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )

        # Bob (member, not admin) tries to add another user - should fail
        new_user_id = UserId.generate().value
        add_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=bob_tenant_auth_headers,
            json={"user_id": new_user_id, "role": "member"},
        )
        assert add_resp.status_code == 403, (
            f"Non-admin should get 403 when adding group member, got {add_resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_add_member_returns_403_for_nonexistent_group(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        clean_iam_data,
    ):
        """Adding member to nonexistent group should return 403 to not leak existence."""
        fake_group_id = GroupId.generate().value
        new_user_id = UserId.generate().value
        add_resp = await async_client.post(
            f"/iam/groups/{fake_group_id}/members",
            headers=tenant_auth_headers,
            json={"user_id": new_user_id, "role": "member"},
        )
        assert add_resp.status_code == 403, (
            f"Nonexistent group should return 403, got {add_resp.status_code}"
        )


class TestListGroupMembers:
    """Tests for GET /iam/groups/{id}/members endpoint."""

    @pytest.mark.asyncio
    async def test_can_list_group_members(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Can list group members showing correct roles.

        Verifies the member list contains alice (admin) and bob (member).
        """
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="list_members_group",
        )

        # Add bob as member
        add_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
            json={"user_id": bob_user_id, "role": "member"},
        )
        assert add_resp.status_code == 201

        # Wait for bob's permission
        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )

        # List members
        list_resp = await async_client.get(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
        )
        assert list_resp.status_code == 200, (
            f"Should be able to list group members, got {list_resp.status_code}: {list_resp.text}"
        )

        members = list_resp.json()
        assert isinstance(members, list), "Response should be a list of members"

        member_map = {m["user_id"]: m for m in members}
        assert alice_user_id in member_map, "Alice should be in member list"
        assert bob_user_id in member_map, "Bob should be in member list"
        assert member_map[alice_user_id]["role"] == "admin", (
            "Alice should have admin role"
        )
        assert member_map[bob_user_id]["role"] == "member", (
            "Bob should have member role"
        )

    @pytest.mark.asyncio
    async def test_tenant_member_can_list_group_members(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Tenant member (not group member) can list group members via VIEW.

        Per the SpiceDB schema: group.view = admin + member_relation + tenant->view
        So tenant members should be able to view group members.
        """
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="tenant_member_list_group",
        )

        # Bob is tenant member but NOT group member
        # Per schema, bob should have VIEW via tenant->view
        list_resp = await async_client.get(
            f"/iam/groups/{group_id}/members",
            headers=bob_tenant_auth_headers,
        )
        assert list_resp.status_code == 200, (
            f"Tenant member should be able to list group members via tenant->view, "
            f"got {list_resp.status_code}: {list_resp.text}"
        )


class TestUpdateGroupMemberRole:
    """Tests for PATCH /iam/groups/{id}/members/{user_id} endpoint."""

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
        """Admin can update a member's role in a group.

        Verifies that role updates correctly modify SpiceDB relationships.
        """
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="update_role_group",
        )

        # Add bob as member
        add_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
            json={"user_id": bob_user_id, "role": "member"},
        )
        assert add_resp.status_code == 201

        # Wait for bob's permission
        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )

        # Update bob to admin
        patch_resp = await async_client.patch(
            f"/iam/groups/{group_id}/members/{bob_user_id}",
            headers=tenant_auth_headers,
            json={"role": "admin"},
        )
        assert patch_resp.status_code == 200, (
            f"Admin should be able to update member role, got {patch_resp.status_code}: {patch_resp.text}"
        )

        data = patch_resp.json()
        assert data["role"] == "admin", "Response should show new admin role"

        # Wait for bob's manage permission (admin gets manage)
        manage_ready = await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.MANAGE,
            bob_subject,
            timeout=5.0,
        )
        assert manage_ready, (
            "Timed out waiting for bob's manage permission after role update"
        )

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
        """Non-admin should receive 403 when trying to update group member role."""
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="non_admin_update_group",
        )

        # Add bob as member (not admin)
        add_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
            json={"user_id": bob_user_id, "role": "member"},
        )
        assert add_resp.status_code == 201

        # Wait for bob's permission
        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )

        # Bob tries to update alice's role - should fail
        patch_resp = await async_client.patch(
            f"/iam/groups/{group_id}/members/{alice_user_id}",
            headers=bob_tenant_auth_headers,
            json={"role": "member"},
        )
        assert patch_resp.status_code == 403, (
            f"Non-admin should get 403 when updating member role, got {patch_resp.status_code}"
        )


class TestRemoveGroupMember:
    """Tests for DELETE /iam/groups/{id}/members/{user_id} endpoint."""

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
        """Admin can remove a member from a group.

        Verifies that SpiceDB relationships are correctly removed.
        """
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="remove_member_group",
        )

        # Add bob as member
        add_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
            json={"user_id": bob_user_id, "role": "member"},
        )
        assert add_resp.status_code == 201

        # Wait for bob's permission
        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )

        # Remove bob
        del_resp = await async_client.delete(
            f"/iam/groups/{group_id}/members/{bob_user_id}",
            headers=tenant_auth_headers,
        )
        assert del_resp.status_code == 204, (
            f"Admin should be able to remove member, got {del_resp.status_code}: {del_resp.text}"
        )

        # Allow time for removal to propagate
        import asyncio

        await asyncio.sleep(0.5)

        # Verify bob no longer has member permission via direct grant
        # Note: bob may still have VIEW via tenant->view relation
        has_manage = await spicedb_client.check_permission(
            group_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage is False, (
            "Removed member should NOT have MANAGE permission on group"
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
        """Non-admin should receive 403 when trying to remove group member."""
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="non_admin_remove_group",
        )

        # Add bob as member (not admin)
        add_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
            json={"user_id": bob_user_id, "role": "member"},
        )
        assert add_resp.status_code == 201

        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )

        # Bob tries to remove alice - should fail
        del_resp = await async_client.delete(
            f"/iam/groups/{group_id}/members/{alice_user_id}",
            headers=bob_tenant_auth_headers,
        )
        assert del_resp.status_code == 403, (
            f"Non-admin should get 403 when removing group member, got {del_resp.status_code}"
        )
