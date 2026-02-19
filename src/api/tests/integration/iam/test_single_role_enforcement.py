"""Integration tests for single role enforcement pattern.

Tests that adding a member with a different role auto-replaces the old role,
ensuring users can only have one role per resource.

AIHCM-160: Authorization integration tests for single role enforcement.
"""

import pytest
import pytest_asyncio

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from iam.dependencies.multi_tenant_mode import _get_single_tenant_mode
from main import app
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from tests.integration.iam.conftest import (
    create_child_workspace,
    create_group,
    ensure_user_provisioned,
    wait_for_permission,
)

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support.

    Overrides single tenant mode for tenant creation tests.
    """
    app.dependency_overrides[_get_single_tenant_mode] = lambda: False
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    app.dependency_overrides.pop(_get_single_tenant_mode, None)


class TestWorkspaceSingleRole:
    """Tests for single role enforcement on workspace members."""

    @pytest.mark.asyncio
    async def test_adding_user_with_different_role_replaces_old_role(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Adding a user with a different role should replace the old role.

        Bob starts as 'member' (view-only) and is changed to 'editor'.
        After the update, bob should have EDIT but not MANAGE, and the
        old 'member' role should be removed.
        """
        # JIT-provision bob so the member-exists validation passes
        await ensure_user_provisioned(async_client, bob_tenant_auth_headers)

        ws_id = await create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="single_role_ws",
        )

        # Add bob as member
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

        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)

        # Wait for member permission
        view_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )
        assert view_ready, "Bob should have VIEW after being added as member"

        # Verify bob does NOT have EDIT as member
        has_edit_before = await spicedb_client.check_permission(
            ws_resource,
            Permission.EDIT,
            bob_subject,
        )
        assert has_edit_before is False, (
            "Member (view-only) should NOT have EDIT permission"
        )

        # Update bob to editor (role replacement via PATCH)
        patch_resp = await async_client.patch(
            f"/iam/workspaces/{ws_id}/members/{bob_user_id}?member_type=user",
            headers=tenant_auth_headers,
            json={"role": "editor"},
        )
        assert patch_resp.status_code == 200, (
            f"Role update should succeed, got {patch_resp.status_code}: {patch_resp.text}"
        )

        # Wait for editor permission
        edit_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )
        assert edit_ready, "Bob should have EDIT after role update to editor"

        # Verify bob has EDIT but not MANAGE (not admin)
        has_edit = await spicedb_client.check_permission(
            ws_resource,
            Permission.EDIT,
            bob_subject,
        )
        assert has_edit is True, (
            "Bob should have EDIT permission after role update to editor"
        )

        has_manage = await spicedb_client.check_permission(
            ws_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage is False, "Bob should NOT have MANAGE permission as editor"


class TestGroupSingleRole:
    """Tests for single role enforcement on group members."""

    @pytest.mark.asyncio
    async def test_adding_user_with_different_group_role_replaces_old(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Adding a user with a different group role should replace the old role.

        Bob starts as 'member' and is changed to 'admin'.
        After the update, bob should have MANAGE (admin gets manage).
        """
        group_id = await create_group(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="single_role_group",
        )

        # Add bob as member
        add_resp = await async_client.post(
            f"/iam/groups/{group_id}/members",
            headers=tenant_auth_headers,
            json={"user_id": bob_user_id, "role": "member"},
        )
        assert add_resp.status_code == 201

        group_resource = format_resource(ResourceType.GROUP, group_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)

        # Wait for member permission
        view_ready = await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )
        assert view_ready

        # Verify bob does NOT have MANAGE as member
        has_manage_before = await spicedb_client.check_permission(
            group_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage_before is False, (
            "Group member should NOT have MANAGE permission"
        )

        # Update bob to admin (role replacement via PATCH)
        patch_resp = await async_client.patch(
            f"/iam/groups/{group_id}/members/{bob_user_id}",
            headers=tenant_auth_headers,
            json={"role": "admin"},
        )
        assert patch_resp.status_code == 200, (
            f"Role update should succeed, got {patch_resp.status_code}: {patch_resp.text}"
        )

        # Wait for manage permission (admin gets manage)
        manage_ready = await wait_for_permission(
            spicedb_client,
            group_resource,
            Permission.MANAGE,
            bob_subject,
            timeout=5.0,
        )
        assert manage_ready, "Bob should have MANAGE after role update to admin"


class TestTenantSingleRole:
    """Tests for single role enforcement on tenant members."""

    @pytest.mark.asyncio
    async def test_adding_user_with_different_tenant_role_replaces_old(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Adding a user with a different tenant role should replace the old role.

        Bob starts as 'member' and is promoted to 'admin'.
        After the update, bob should have ADMINISTRATE.
        """
        # Create tenant (alice is admin)
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Single Role Tenant Test"},
            headers=tenant_auth_headers,
        )
        assert create_resp.status_code == 201
        tenant_id = create_resp.json()["id"]

        # Wait for alice's admin permission
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id)
        alice_subject = format_subject(ResourceType.USER, alice_user_id)
        await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.ADMINISTRATE,
            alice_subject,
            timeout=5.0,
        )

        # Add bob as regular member
        add_resp = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": bob_user_id, "role": "member"},
            headers=tenant_auth_headers,
        )
        assert add_resp.status_code == 201

        bob_subject = format_subject(ResourceType.USER, bob_user_id)

        # Wait for bob's VIEW permission
        await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )

        # Verify bob does NOT have ADMINISTRATE as member
        has_admin_before = await spicedb_client.check_permission(
            tenant_resource,
            Permission.ADMINISTRATE,
            bob_subject,
        )
        assert has_admin_before is False, (
            "Regular member should NOT have ADMINISTRATE permission"
        )

        # Promote bob to admin via POST (no PATCH endpoint for tenant members;
        # POST with an existing user_id triggers role replacement).
        promote_resp = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": bob_user_id, "role": "admin"},
            headers=tenant_auth_headers,
        )
        assert promote_resp.status_code == 201, (
            f"Role replacement should succeed, got {promote_resp.status_code}: {promote_resp.text}"
        )

        # Wait for bob's ADMINISTRATE permission
        admin_ready = await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.ADMINISTRATE,
            bob_subject,
            timeout=5.0,
        )
        assert admin_ready, (
            "Bob should have ADMINISTRATE after role replacement to admin"
        )

        # Verify bob has ADMINISTRATE (admin gets administrate)
        has_admin_after = await spicedb_client.check_permission(
            tenant_resource,
            Permission.ADMINISTRATE,
            bob_subject,
        )
        assert has_admin_after is True, (
            "Bob should have ADMINISTRATE permission after role replacement"
        )
