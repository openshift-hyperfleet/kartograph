"""Integration tests for tenant authorization enforcement.

Tests tenant listing filtered by VIEW permission, tenant creation auto-grants,
and auto-grant/revoke of root workspace access on tenant role changes.

AIHCM-160: Authorization integration tests for tenant authorization.
"""

import asyncio

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
from tests.integration.iam.conftest import wait_for_permission

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support.

    Overrides _get_single_tenant_mode to return False so that tenant
    CRUD routes (POST, DELETE) are not blocked by the single-tenant gate.
    """
    app.dependency_overrides[_get_single_tenant_mode] = lambda: False
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    app.dependency_overrides.pop(_get_single_tenant_mode, None)


class TestTenantListingFiltered:
    """Tests for tenant listing filtered by VIEW permission."""

    @pytest.mark.asyncio
    async def test_tenant_listing_only_shows_tenants_user_is_member_of(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Tenant listing should filter by VIEW permission.

        Alice creates "Acme Corp" - she gets admin via create_tenant.
        Bob is a member of the default tenant but NOT Acme Corp.
        Bob should not see Acme Corp in his tenant listing.
        """
        # Alice creates a new tenant
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp Listing Test"},
            headers=tenant_auth_headers,
        )
        assert create_resp.status_code == 201, (
            f"Failed to create tenant: {create_resp.text}"
        )
        acme_tenant_id = create_resp.json()["id"]

        # Wait for alice's admin permission on Acme Corp
        acme_resource = format_resource(ResourceType.TENANT, acme_tenant_id)
        alice_subject = format_subject(ResourceType.USER, alice_user_id)
        await wait_for_permission(
            spicedb_client,
            acme_resource,
            Permission.ADMINISTRATE,
            alice_subject,
            timeout=5.0,
        )

        # Bob lists tenants - should see default but NOT Acme Corp
        bob_resp = await async_client.get(
            "/iam/tenants",
            headers=bob_tenant_auth_headers,
        )
        assert bob_resp.status_code == 200

        bob_tenant_ids = [t["id"] for t in bob_resp.json()]
        assert acme_tenant_id not in bob_tenant_ids, (
            f"Bob should NOT see Acme Corp (he is not a member). "
            f"Got tenant IDs: {bob_tenant_ids}"
        )

    @pytest.mark.asyncio
    async def test_bob_only_sees_tenants_he_is_member_of(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        default_tenant_id: str,
        clean_iam_data,
    ):
        """Bob should see only the default tenant (where he is member).

        Alice creates another tenant; bob should only see default tenant.
        """
        # Alice creates a new tenant (bob is NOT added)
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Bob Exclusion Test"},
            headers=tenant_auth_headers,
        )
        assert create_resp.status_code == 201

        # Bob lists tenants
        bob_resp = await async_client.get(
            "/iam/tenants",
            headers=bob_tenant_auth_headers,
        )
        assert bob_resp.status_code == 200

        bob_tenant_ids = [t["id"] for t in bob_resp.json()]
        assert default_tenant_id in bob_tenant_ids, (
            "Bob should see the default tenant (he is a member)"
        )


class TestTenantCreationAutoGrant:
    """Tests for auto-grant behavior on tenant creation."""

    @pytest.mark.asyncio
    async def test_tenant_creation_grants_creator_admin_on_tenant(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Creating a tenant should auto-grant creator admin on tenant.

        The creator is automatically added as admin via add_member in
        create_tenant, which writes an outbox event.
        """
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Admin Grant Test"},
            headers=tenant_auth_headers,
        )
        assert create_resp.status_code == 201
        tenant_id = create_resp.json()["id"]

        # Wait for admin permission to propagate
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id)
        alice_subject = format_subject(ResourceType.USER, alice_user_id)
        admin_ready = await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.ADMINISTRATE,
            alice_subject,
            timeout=5.0,
        )
        assert admin_ready, (
            "Creator should have ADMINISTRATE permission on new tenant after creation"
        )

    @pytest.mark.asyncio
    async def test_tenant_creation_grants_creator_admin_on_root_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Creating a tenant should auto-grant creator admin on root workspace.

        The create_tenant service creates a root workspace and adds the
        creator as admin on it.
        """
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Root WS Grant Test"},
            headers=tenant_auth_headers,
        )
        assert create_resp.status_code == 201
        tenant_id = create_resp.json()["id"]

        # We need to find the root workspace for this tenant
        # First wait for tenant admin
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id)
        alice_subject = format_subject(ResourceType.USER, alice_user_id)
        await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.ADMINISTRATE,
            alice_subject,
            timeout=5.0,
        )

        # Get root workspace by listing workspaces with alice's tenant context
        # We need to use a custom tenant header for the new tenant
        new_tenant_headers = {
            **tenant_auth_headers,
            "X-Tenant-ID": tenant_id,
        }

        ws_resp = await async_client.get(
            "/iam/workspaces",
            headers=new_tenant_headers,
        )
        assert ws_resp.status_code == 200

        workspaces = ws_resp.json()["workspaces"]
        root_workspaces = [w for w in workspaces if w["is_root"]]

        assert len(root_workspaces) > 0, (
            "Root workspace should be returned in workspace listing for tenant admin"
        )
        root_ws_id = root_workspaces[0]["id"]
        ws_resource = format_resource(ResourceType.WORKSPACE, root_ws_id)

        # Check alice has MANAGE on root workspace
        manage_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.MANAGE,
            alice_subject,
            timeout=5.0,
        )
        assert manage_ready, "Creator should have MANAGE permission on root workspace"

    @pytest.mark.asyncio
    async def test_tenant_creation_creates_root_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Creating a tenant should automatically create a root workspace."""
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Root WS Creation Test"},
            headers=tenant_auth_headers,
        )
        assert create_resp.status_code == 201
        tenant_id = create_resp.json()["id"]

        # Wait for tenant admin
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id)
        alice_subject = format_subject(ResourceType.USER, alice_user_id)
        await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.ADMINISTRATE,
            alice_subject,
            timeout=5.0,
        )

        # List workspaces for the new tenant
        new_tenant_headers = {
            **tenant_auth_headers,
            "X-Tenant-ID": tenant_id,
        }
        ws_resp = await async_client.get(
            "/iam/workspaces",
            headers=new_tenant_headers,
        )
        assert ws_resp.status_code == 200

        workspaces = ws_resp.json()["workspaces"]
        root_workspaces = [w for w in workspaces if w["is_root"]]
        assert len(root_workspaces) == 1, (
            f"Tenant creation should create exactly one root workspace, "
            f"got {len(root_workspaces)}"
        )
        assert root_workspaces[0]["is_root"] is True


class TestAutoGrantRootWorkspaceAccess:
    """Tests for auto-grant/revoke root workspace access on tenant role changes."""

    @pytest.mark.asyncio
    async def test_adding_tenant_admin_grants_root_workspace_admin(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Adding a user as tenant admin should auto-grant root workspace admin.

        When alice adds bob as tenant admin, bob should automatically get
        admin on the root workspace.
        """
        # Create tenant (alice is admin)
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Auto Grant Admin Test"},
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

        # Add bob as tenant admin
        add_resp = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": bob_user_id, "role": "admin"},
            headers=tenant_auth_headers,
        )
        assert add_resp.status_code == 201, (
            f"Should be able to add tenant admin, got {add_resp.status_code}: {add_resp.text}"
        )

        # Wait for bob's tenant admin permission
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.ADMINISTRATE,
            bob_subject,
            timeout=5.0,
        )

        # Get root workspace
        new_tenant_headers = {
            **tenant_auth_headers,
            "X-Tenant-ID": tenant_id,
        }
        ws_resp = await async_client.get(
            "/iam/workspaces",
            headers=new_tenant_headers,
        )
        assert ws_resp.status_code == 200
        root_workspaces = [w for w in ws_resp.json()["workspaces"] if w["is_root"]]

        assert len(root_workspaces) > 0, (
            "Root workspace should be returned in workspace listing for tenant admin"
        )
        root_ws_id = root_workspaces[0]["id"]
        ws_resource = format_resource(ResourceType.WORKSPACE, root_ws_id)

        # Verify bob has MANAGE on root workspace
        manage_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.MANAGE,
            bob_subject,
            timeout=5.0,
        )
        assert manage_ready, (
            "Tenant admin should have MANAGE permission on root workspace"
        )

    @pytest.mark.asyncio
    async def test_adding_tenant_member_does_not_grant_root_workspace_admin(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Adding a user as regular tenant member should NOT grant root workspace admin.

        Regular members get VIEW on workspaces via tenant->view, but not MANAGE.
        """
        # Create tenant (alice is admin)
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "No Admin Grant Test"},
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

        # Add bob as regular member (not admin)
        add_resp = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": bob_user_id, "role": "member"},
            headers=tenant_auth_headers,
        )
        assert add_resp.status_code == 201

        # Wait for bob's tenant view permission
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.VIEW,
            bob_subject,
            timeout=5.0,
        )

        # Get root workspace
        new_tenant_headers = {
            **tenant_auth_headers,
            "X-Tenant-ID": tenant_id,
        }
        ws_resp = await async_client.get(
            "/iam/workspaces",
            headers=new_tenant_headers,
        )
        assert ws_resp.status_code == 200
        root_workspaces = [w for w in ws_resp.json()["workspaces"] if w["is_root"]]

        assert len(root_workspaces) > 0, (
            "Root workspace should be returned in workspace listing for tenant admin"
        )
        root_ws_id = root_workspaces[0]["id"]
        ws_resource = format_resource(ResourceType.WORKSPACE, root_ws_id)

        # Allow time for any potential auto-grant to propagate
        await asyncio.sleep(0.5)

        # Verify bob does NOT have MANAGE on root workspace
        has_manage = await spicedb_client.check_permission(
            ws_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage is False, (
            "Regular tenant member should NOT have MANAGE permission on root workspace"
        )

        # But bob should have VIEW via tenant->view
        has_view = await spicedb_client.check_permission(
            ws_resource,
            Permission.VIEW,
            bob_subject,
        )
        assert has_view is True, (
            "Regular tenant member should have VIEW permission on root workspace "
            "via tenant->view"
        )

    @pytest.mark.asyncio
    async def test_downgrading_tenant_admin_to_member_revokes_root_workspace_admin(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Downgrading tenant admin to member should revoke root workspace admin.

        When bob is demoted from tenant admin to member, his root workspace
        admin access should be revoked.
        """
        # Create tenant (alice is admin)
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Downgrade Test"},
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

        # Add bob as admin first
        add_resp = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": bob_user_id, "role": "admin"},
            headers=tenant_auth_headers,
        )
        assert add_resp.status_code == 201

        # Wait for bob's admin permission on tenant
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.ADMINISTRATE,
            bob_subject,
            timeout=5.0,
        )

        # Verify bob has MANAGE on root workspace
        new_tenant_headers = {
            **tenant_auth_headers,
            "X-Tenant-ID": tenant_id,
        }
        ws_resp = await async_client.get(
            "/iam/workspaces",
            headers=new_tenant_headers,
        )
        root_workspaces = [w for w in ws_resp.json()["workspaces"] if w["is_root"]]
        assert len(root_workspaces) > 0, "Should have root workspace"
        root_ws_id = root_workspaces[0]["id"]
        ws_resource = format_resource(ResourceType.WORKSPACE, root_ws_id)

        manage_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.MANAGE,
            bob_subject,
            timeout=5.0,
        )
        assert manage_ready, "Bob should have MANAGE before downgrade"

        # Downgrade bob to member (role replacement)
        downgrade_resp = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": bob_user_id, "role": "member"},
            headers=tenant_auth_headers,
        )
        assert downgrade_resp.status_code == 201, (
            f"Should be able to downgrade tenant admin to member, "
            f"got {downgrade_resp.status_code}: {downgrade_resp.text}"
        )

        # Allow time for propagation
        await asyncio.sleep(1.0)

        # Verify bob no longer has MANAGE on root workspace
        has_manage = await spicedb_client.check_permission(
            ws_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage is False, (
            "Downgraded tenant member should NOT have MANAGE on root workspace"
        )

        # Bob should still have VIEW via tenant->view
        has_view = await spicedb_client.check_permission(
            ws_resource,
            Permission.VIEW,
            bob_subject,
        )
        assert has_view is True, (
            "Downgraded tenant member should still have VIEW via tenant->view"
        )

    @pytest.mark.asyncio
    async def test_removing_tenant_member_revokes_root_workspace_access(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Removing a tenant member should revoke their root workspace access.

        When bob is removed from the tenant entirely, he should lose all
        workspace access (both MANAGE and VIEW).
        """
        # Create tenant (alice is admin)
        create_resp = await async_client.post(
            "/iam/tenants",
            json={"name": "Remove Member Test"},
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

        # Add bob as admin
        add_resp = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": bob_user_id, "role": "admin"},
            headers=tenant_auth_headers,
        )
        assert add_resp.status_code == 201

        # Wait for bob's tenant admin permission
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await wait_for_permission(
            spicedb_client,
            tenant_resource,
            Permission.ADMINISTRATE,
            bob_subject,
            timeout=5.0,
        )

        # Get root workspace
        new_tenant_headers = {
            **tenant_auth_headers,
            "X-Tenant-ID": tenant_id,
        }
        ws_resp = await async_client.get(
            "/iam/workspaces",
            headers=new_tenant_headers,
        )
        root_workspaces = [w for w in ws_resp.json()["workspaces"] if w["is_root"]]
        assert len(root_workspaces) > 0
        root_ws_id = root_workspaces[0]["id"]
        ws_resource = format_resource(ResourceType.WORKSPACE, root_ws_id)

        # Verify bob has MANAGE before removal
        manage_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.MANAGE,
            bob_subject,
            timeout=5.0,
        )
        assert manage_ready, "Bob should have MANAGE before removal"

        # Remove bob from tenant entirely
        remove_resp = await async_client.delete(
            f"/iam/tenants/{tenant_id}/members/{bob_user_id}",
            headers=tenant_auth_headers,
        )
        assert remove_resp.status_code == 204, (
            f"Should be able to remove tenant member, "
            f"got {remove_resp.status_code}: {remove_resp.text}"
        )

        # Allow time for propagation
        await asyncio.sleep(1.0)

        # Verify bob has no workspace access
        has_manage = await spicedb_client.check_permission(
            ws_resource,
            Permission.MANAGE,
            bob_subject,
        )
        assert has_manage is False, (
            "Removed tenant member should NOT have MANAGE on root workspace"
        )

        # VIEW should also be gone since bob is no longer a tenant member
        # (no tenant->view path)
        has_view = await spicedb_client.check_permission(
            ws_resource,
            Permission.VIEW,
            bob_subject,
        )
        assert has_view is False, (
            "Removed tenant member should NOT have VIEW on root workspace "
            "(no tenant->view path)"
        )
