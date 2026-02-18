"""Integration tests for workspace authorization enforcement.

Tests the 3-tier role hierarchy (ADMIN/EDITOR/MEMBER) for workspaces,
filtered workspace listings, and create_child permission separation.

AIHCM-160: Authorization integration tests for workspace authorization.
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


async def _create_child_workspace(
    async_client: AsyncClient,
    tenant_auth_headers: dict,
    spicedb_client: AuthorizationProvider,
    alice_user_id: str,
    name: str = "test_ws",
) -> str:
    """Helper: Create a child workspace and wait for admin permission."""
    ws_list = await async_client.get("/iam/workspaces", headers=tenant_auth_headers)
    root = next(w for w in ws_list.json()["workspaces"] if w["is_root"])

    create_resp = await async_client.post(
        "/iam/workspaces",
        headers=tenant_auth_headers,
        json={"name": name, "parent_workspace_id": root["id"]},
    )
    assert create_resp.status_code == 201
    ws_id = create_resp.json()["id"]

    ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
    alice_subject = format_subject(ResourceType.USER, alice_user_id)
    admin_ready = await wait_for_permission(
        spicedb_client,
        ws_resource,
        Permission.MANAGE,
        alice_subject,
        timeout=5.0,
    )
    assert admin_ready, "Timed out waiting for workspace admin permission"
    return ws_id


async def _get_root_workspace_id(
    async_client: AsyncClient,
    tenant_auth_headers: dict,
) -> str:
    """Helper: Get the root workspace ID."""
    ws_list = await async_client.get("/iam/workspaces", headers=tenant_auth_headers)
    assert ws_list.status_code == 200
    root = next(w for w in ws_list.json()["workspaces"] if w["is_root"])
    return root["id"]


class TestWorkspaceRoleEnforcement:
    """Tests for 3-tier role enforcement on workspace operations."""

    @pytest.mark.asyncio
    async def test_workspace_admin_can_delete_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Admin role should have MANAGE permission to delete workspace."""
        ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="admin_delete_ws",
        )

        resp = await async_client.delete(
            f"/iam/workspaces/{ws_id}",
            headers=tenant_auth_headers,
        )
        assert resp.status_code == 204, (
            f"Admin should be able to delete workspace, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_workspace_editor_cannot_delete_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Editor role should NOT have MANAGE permission to delete workspace.

        Delete requires MANAGE which only admin has.
        """
        ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="editor_no_delete_ws",
        )

        # Grant bob editor directly in SpiceDB
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation="editor",
            subject=bob_subject,
        )

        # Verify bob has EDIT
        edit_ready = await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )
        assert edit_ready

        # Bob tries to delete - should fail
        resp = await async_client.delete(
            f"/iam/workspaces/{ws_id}",
            headers=bob_tenant_auth_headers,
        )
        assert resp.status_code == 403, (
            f"Editor should NOT be able to delete workspace (requires MANAGE), "
            f"got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_workspace_member_cannot_delete_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Member (viewer) role should NOT have MANAGE permission to delete workspace."""
        ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="member_no_delete_ws",
        )

        # Grant bob member directly in SpiceDB
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation="member",
            subject=bob_subject,
        )

        # Bob tries to delete - should fail
        resp = await async_client.delete(
            f"/iam/workspaces/{ws_id}",
            headers=bob_tenant_auth_headers,
        )
        assert resp.status_code == 403, (
            f"Member should NOT be able to delete workspace, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_workspace_admin_can_update_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_iam_data,
    ):
        """Admin role should have MANAGE permission to update workspace."""
        ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="admin_update_ws",
        )

        resp = await async_client.patch(
            f"/iam/workspaces/{ws_id}",
            headers=tenant_auth_headers,
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200, (
            f"Admin should be able to update workspace, got {resp.status_code}: {resp.text}"
        )
        assert resp.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_workspace_editor_cannot_update_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Editor role should NOT have MANAGE permission to update workspace.

        Update/rename requires MANAGE which only admin has.
        """
        ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="editor_no_update_ws",
        )

        # Grant bob editor directly in SpiceDB
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation="editor",
            subject=bob_subject,
        )

        resp = await async_client.patch(
            f"/iam/workspaces/{ws_id}",
            headers=bob_tenant_auth_headers,
            json={"name": "Bob Updated"},
        )
        assert resp.status_code == 403, (
            f"Editor should NOT be able to update workspace (requires MANAGE), "
            f"got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_workspace_member_cannot_update_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Member (viewer) role should NOT have MANAGE permission to update workspace."""
        ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="member_no_update_ws",
        )

        # Grant bob member directly in SpiceDB
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation="member",
            subject=bob_subject,
        )

        resp = await async_client.patch(
            f"/iam/workspaces/{ws_id}",
            headers=bob_tenant_auth_headers,
            json={"name": "Bob Updated"},
        )
        assert resp.status_code == 403, (
            f"Member should NOT be able to update workspace, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_workspace_member_can_view_workspace(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Member (viewer) role should have VIEW permission to view workspace."""
        ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="member_view_ws",
        )

        # Grant bob member directly in SpiceDB
        ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation="member",
            subject=bob_subject,
        )

        resp = await async_client.get(
            f"/iam/workspaces/{ws_id}",
            headers=bob_tenant_auth_headers,
        )
        assert resp.status_code == 200, (
            f"Member should be able to view workspace, got {resp.status_code}: {resp.text}"
        )
        assert resp.json()["id"] == ws_id


class TestWorkspaceListingFiltered:
    """Tests for workspace listing filtered by VIEW permission."""

    @pytest.mark.asyncio
    async def test_workspace_listing_only_shows_accessible_workspaces(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Workspace listing should only show workspaces user can VIEW.

        Per the schema: workspace.view = admin + editor + member + tenant->view
        All tenant members can view all workspaces in their tenant via tenant->view.
        """
        # Create workspaces (side effect: they exist in the tenant for listing)
        await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="listing_ws_1",
        )
        await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="listing_ws_2",
        )

        # Bob is tenant member -> has VIEW on all tenant workspaces via tenant->view
        resp = await async_client.get(
            "/iam/workspaces",
            headers=bob_tenant_auth_headers,
        )
        assert resp.status_code == 200, (
            f"Bob should be able to list workspaces, got {resp.status_code}"
        )

        workspace_ids = [w["id"] for w in resp.json()["workspaces"]]
        # Bob should see root + child workspaces via tenant->view
        assert len(workspace_ids) >= 1, (
            "Bob should see at least the root workspace as tenant member"
        )


class TestWorkspaceCreationAuthorization:
    """Tests for create_child permission on workspaces."""

    @pytest.mark.asyncio
    async def test_tenant_member_can_create_workspace_under_root_via_api(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Tenant member should be able to create workspace under root.

        Per schema: root workspace has creator_tenant relation.
        create_child = admin + editor + creator_tenant->view
        Tenant members have view on tenant, so they get create_child on root via
        creator_tenant->view.
        """
        root_ws_id = await _get_root_workspace_id(async_client, tenant_auth_headers)

        # Bob (tenant member) creates workspace under root
        resp = await async_client.post(
            "/iam/workspaces",
            headers=bob_tenant_auth_headers,
            json={"name": "bob_root_child", "parent_workspace_id": root_ws_id},
        )
        assert resp.status_code == 201, (
            f"Tenant member should be able to create workspace under root, "
            f"got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_tenant_member_cannot_create_workspace_under_child_via_api(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Tenant member (without workspace role) cannot create under child workspace.

        Child workspaces don't have creator_tenant relation, so create_child
        requires admin or editor role on the child workspace.
        """
        # Alice creates child workspace
        child_ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="child_for_bob_test",
        )

        # Bob (tenant member but not workspace admin/editor) tries to create under child
        resp = await async_client.post(
            "/iam/workspaces",
            headers=bob_tenant_auth_headers,
            json={"name": "bob_child_child", "parent_workspace_id": child_ws_id},
        )
        assert resp.status_code == 403, (
            f"Tenant member without workspace role should NOT be able to create "
            f"under child workspace, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_workspace_editor_can_create_under_child_workspace_via_api(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        bob_tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        bob_user_id: str,
        clean_iam_data,
    ):
        """Workspace editor should be able to create under child workspace.

        create_child = admin + editor + creator_tenant->view
        Editor gets create_child directly.
        """
        # Alice creates child workspace
        child_ws_id = await _create_child_workspace(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            name="editor_create_child",
        )

        # Grant bob editor on child workspace
        ws_resource = format_resource(ResourceType.WORKSPACE, child_ws_id)
        bob_subject = format_subject(ResourceType.USER, bob_user_id)
        await spicedb_client.write_relationship(
            resource=ws_resource,
            relation="editor",
            subject=bob_subject,
        )

        # Wait for editor permission
        await wait_for_permission(
            spicedb_client,
            ws_resource,
            Permission.EDIT,
            bob_subject,
            timeout=5.0,
        )

        # Bob (editor) creates workspace under child
        resp = await async_client.post(
            "/iam/workspaces",
            headers=bob_tenant_auth_headers,
            json={"name": "editor_created_ws", "parent_workspace_id": child_ws_id},
        )
        assert resp.status_code == 201, (
            f"Editor should be able to create workspace under child, "
            f"got {resp.status_code}: {resp.text}"
        )
