"""Integration tests for Workspace API endpoints.

Tests the workspace CRUD operations including the critical behavior
that deleting a parent workspace with children should fail.

Note: The workspace service now grants the creator admin access via a
WorkspaceMemberAdded event written to the outbox. However, SpiceDB
relationships are processed asynchronously by the outbox worker. In
integration tests, the ``grant_workspace_admin`` fixture writes admin
relationships to SpiceDB synchronously so that subsequent operations
(create children, delete) succeed permission checks without waiting
for outbox processing.
"""

import pytest
import pytest_asyncio
from collections.abc import Callable, Coroutine
from typing import Any
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support.

    Uses LifespanManager to ensure app lifespan (database engine init)
    runs before tests and cleanup runs after.
    """
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


class TestWorkspaceCreation:
    """Tests for workspace creation."""

    @pytest.mark.asyncio
    async def test_creates_child_workspace(
        self, async_client: AsyncClient, tenant_auth_headers: dict, clean_iam_data
    ):
        """Test creating a child workspace under root."""
        # Get root workspace
        resp = await async_client.get("/iam/workspaces", headers=tenant_auth_headers)
        assert resp.status_code == 200
        workspaces = resp.json()["workspaces"]
        root = next((w for w in workspaces if w["is_root"]), None)
        assert root is not None, "Root workspace should exist"

        # Create child workspace
        resp = await async_client.post(
            "/iam/workspaces",
            headers=tenant_auth_headers,
            json={"name": "test_child", "parent_workspace_id": root["id"]},
        )
        assert resp.status_code == 201
        child = resp.json()
        assert child["name"] == "test_child"
        assert child["parent_workspace_id"] == root["id"]
        assert child["is_root"] is False


class TestWorkspaceDeletion:
    """Tests for workspace deletion behavior."""

    @pytest.mark.asyncio
    async def test_cannot_delete_parent_with_children(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        clean_iam_data,
        grant_workspace_admin: Callable[[str], Coroutine[Any, Any, None]],
    ):
        """Test that deleting a parent workspace with children fails with 409.

        This is a critical business rule: workspaces form a hierarchy and
        deleting a parent would orphan children. The database FK constraint
        (ON DELETE RESTRICT) should prevent this, and the API should return
        a 409 Conflict error.
        """
        # Get root workspace
        resp = await async_client.get("/iam/workspaces", headers=tenant_auth_headers)
        assert resp.status_code == 200
        root = next((w for w in resp.json()["workspaces"] if w["is_root"]), None)
        assert root is not None

        # Create parent workspace (child of root)
        resp = await async_client.post(
            "/iam/workspaces",
            headers=tenant_auth_headers,
            json={"name": "parent_ws", "parent_workspace_id": root["id"]},
        )
        assert resp.status_code == 201
        parent = resp.json()

        # Grant admin on parent so Alice can create children under it and delete it
        await grant_workspace_admin(parent["id"])

        # Create child workspace (child of parent)
        resp = await async_client.post(
            "/iam/workspaces",
            headers=tenant_auth_headers,
            json={"name": "child_ws", "parent_workspace_id": parent["id"]},
        )
        assert resp.status_code == 201
        child = resp.json()

        # Grant admin on child so Alice can delete it during cleanup
        await grant_workspace_admin(child["id"])

        # Attempt to delete parent - should fail with 409
        resp = await async_client.delete(
            f"/iam/workspaces/{parent['id']}", headers=tenant_auth_headers
        )
        assert resp.status_code == 409, (
            f"Expected 409 Conflict when deleting parent with children, "
            f"got {resp.status_code}: {resp.text}"
        )
        assert "children" in resp.json()["detail"].lower()

        # Cleanup: delete child first, then parent
        resp = await async_client.delete(
            f"/iam/workspaces/{child['id']}", headers=tenant_auth_headers
        )
        assert resp.status_code == 204

        resp = await async_client.delete(
            f"/iam/workspaces/{parent['id']}", headers=tenant_auth_headers
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_can_delete_workspace_without_children(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        clean_iam_data,
        grant_workspace_admin: Callable[[str], Coroutine[Any, Any, None]],
    ):
        """Test that deleting a workspace without children succeeds."""
        # Get root workspace
        resp = await async_client.get("/iam/workspaces", headers=tenant_auth_headers)
        assert resp.status_code == 200
        root = next((w for w in resp.json()["workspaces"] if w["is_root"]), None)
        assert root is not None

        # Create a workspace
        resp = await async_client.post(
            "/iam/workspaces",
            headers=tenant_auth_headers,
            json={"name": "leaf_ws", "parent_workspace_id": root["id"]},
        )
        assert resp.status_code == 201
        workspace = resp.json()

        # Grant admin on workspace so Alice can delete it
        await grant_workspace_admin(workspace["id"])

        # Delete it - should succeed
        resp = await async_client.delete(
            f"/iam/workspaces/{workspace['id']}", headers=tenant_auth_headers
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_cannot_delete_root_workspace(
        self, async_client: AsyncClient, tenant_auth_headers: dict, clean_iam_data
    ):
        """Test that deleting the root workspace fails with 409."""
        # Get root workspace
        resp = await async_client.get("/iam/workspaces", headers=tenant_auth_headers)
        assert resp.status_code == 200
        root = next((w for w in resp.json()["workspaces"] if w["is_root"]), None)
        assert root is not None

        # Attempt to delete root - should fail
        resp = await async_client.delete(
            f"/iam/workspaces/{root['id']}", headers=tenant_auth_headers
        )
        assert resp.status_code == 409
