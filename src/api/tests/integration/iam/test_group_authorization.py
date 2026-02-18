"""Integration tests for group authorization enforcement.

Tests admin vs member role enforcement for group operations,
and filtered group listings.

AIHCM-160: Authorization integration tests for group authorization.
"""

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
    """Helper: Create a group and wait for admin permission."""
    create_resp = await async_client.post(
        "/iam/groups",
        headers=tenant_auth_headers,
        json={"name": name},
    )
    assert create_resp.status_code == 201
    group_id = create_resp.json()["id"]

    group_resource = format_resource(ResourceType.GROUP, group_id)
    alice_subject = format_subject(ResourceType.USER, alice_user_id)
    admin_ready = await wait_for_permission(
        spicedb_client,
        group_resource,
        Permission.MANAGE,
        alice_subject,
        timeout=5.0,
    )
    assert admin_ready, "Timed out waiting for group admin permission"
    return group_id


class TestGroupRoleEnforcement:
    """Tests for group admin vs member role enforcement."""

    @pytest.mark.asyncio
    async def test_group_admin_can_delete_group(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Group admin should be able to delete group (requires MANAGE)."""
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="admin_delete_group",
        )

        resp = await async_client.delete(
            f"/iam/groups/{group_id}",
            headers=tenant_auth_headers,
        )
        assert resp.status_code == 204, (
            f"Admin should be able to delete group, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_group_member_cannot_delete_group(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Group member (not admin) should NOT be able to delete group."""
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="member_no_delete_group",
        )

        # Add bob as regular member (not admin)
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

        # Bob tries to delete - should fail
        resp = await async_client.delete(
            f"/iam/groups/{group_id}",
            headers=bob_tenant_auth_headers,
        )
        assert resp.status_code == 403, (
            f"Group member should NOT be able to delete group, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_group_admin_can_rename_group(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Group admin should be able to rename group (requires MANAGE)."""
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="admin_rename_group",
        )

        resp = await async_client.patch(
            f"/iam/groups/{group_id}",
            headers=tenant_auth_headers,
            json={"name": "Renamed Group"},
        )
        assert resp.status_code == 200, (
            f"Admin should be able to rename group, got {resp.status_code}: {resp.text}"
        )
        assert resp.json()["name"] == "Renamed Group"

    @pytest.mark.asyncio
    async def test_group_member_cannot_rename_group(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Group member (not admin) should NOT be able to rename group."""
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="member_no_rename_group",
        )

        # Add bob as regular member
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

        # Bob tries to rename - should fail
        resp = await async_client.patch(
            f"/iam/groups/{group_id}",
            headers=bob_tenant_auth_headers,
            json={"name": "Bob Renamed"},
        )
        assert resp.status_code == 403, (
            f"Group member should NOT be able to rename group, got {resp.status_code}"
        )


class TestGroupListingFiltered:
    """Tests for group listing filtered by VIEW permission."""

    @pytest.mark.asyncio
    async def test_group_listing_only_shows_accessible_groups(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Group listing should show groups visible via tenant->view.

        Per schema: group.view = admin + member_relation + tenant->view
        Bob is a tenant member, so he should see groups in his tenant.
        """
        # Alice creates a group
        group_id = await _create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="visible_group",
        )

        # Bob lists groups - should see alice's group via tenant->view
        resp = await async_client.get(
            "/iam/groups",
            headers=bob_tenant_auth_headers,
        )
        assert resp.status_code == 200, (
            f"Bob should be able to list groups, got {resp.status_code}"
        )

        group_ids = [g["id"] for g in resp.json()]
        assert group_id in group_ids, (
            f"Bob should see alice's group {group_id} via tenant->view, "
            f"but only sees {group_ids}"
        )
