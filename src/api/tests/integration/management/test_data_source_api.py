"""Integration tests for Data Source API endpoints.

Tests the full stack: HTTP request -> route -> DI -> service ->
SpiceDB + PostgreSQL -> response.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from shared_kernel.authorization.protocols import AuthorizationProvider
from tests.integration.management.conftest import (
    grant_ds_permission,
    grant_kg_permission,
)

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


async def _get_root_workspace_id(
    async_client: AsyncClient, tenant_auth_headers: dict
) -> str:
    """Get the root workspace ID for the default tenant."""
    resp = await async_client.get("/iam/workspaces", headers=tenant_auth_headers)
    assert resp.status_code == 200
    workspaces = resp.json()["workspaces"]
    root = next((w for w in workspaces if w["is_root"]), None)
    assert root is not None, "Root workspace should exist"
    return root["id"]


async def _create_kg(
    async_client: AsyncClient,
    tenant_auth_headers: dict,
    spicedb_client: AuthorizationProvider,
    alice_user_id: str,
    workspace_id: str,
    name: str = "Test KG for DS",
) -> str:
    """Create a KG and set up SpiceDB permissions. Returns the KG ID."""
    resp = await async_client.post(
        f"/management/workspaces/{workspace_id}/knowledge-graphs",
        headers=tenant_auth_headers,
        json={"name": name},
    )
    assert resp.status_code == 201, f"Failed to create KG: {resp.text}"
    kg_id = resp.json()["id"]

    await grant_kg_permission(spicedb_client, alice_user_id, kg_id, workspace_id)
    return kg_id


class TestDataSourceCreation:
    """Tests for POST /management/knowledge-graphs/{kg_id}/data-sources."""

    @pytest.mark.asyncio
    async def test_creates_data_source(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test creating a DS via API returns 201 with correct fields."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)
        kg_id = await _create_kg(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            workspace_id,
        )

        resp = await async_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            headers=tenant_auth_headers,
            json={
                "name": "Test DS",
                "adapter_type": "github",
                "connection_config": {"owner": "test", "repo": "test-repo"},
            },
        )

        assert resp.status_code == 201, f"Unexpected: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["name"] == "Test DS"
        assert data["adapter_type"] == "github"
        assert data["knowledge_graph_id"] == kg_id
        assert data["has_credentials"] is False
        assert data["schedule_type"] == "manual"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_creates_data_source_with_credentials(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test creating a DS with credentials sets has_credentials=true."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)
        kg_id = await _create_kg(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            workspace_id,
            name="KG with creds",
        )

        resp = await async_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            headers=tenant_auth_headers,
            json={
                "name": "DS with creds",
                "adapter_type": "github",
                "connection_config": {"owner": "test", "repo": "test-repo"},
                "credentials": {"token": "ghp_secrettoken123"},
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["has_credentials"] is True
        # Credentials should NOT be in response
        assert "credentials" not in data
        assert "credentials_path" not in data


class TestDataSourceTriggerSync:
    """Tests for POST /management/data-sources/{ds_id}/sync."""

    @pytest.mark.asyncio
    async def test_trigger_sync_returns_202(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test triggering a sync returns 202 with sync run details."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)
        kg_id = await _create_kg(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            workspace_id,
            name="KG for sync",
        )

        # Create DS
        resp = await async_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            headers=tenant_auth_headers,
            json={
                "name": "Sync DS",
                "adapter_type": "github",
                "connection_config": {"owner": "test", "repo": "test-repo"},
            },
        )
        assert resp.status_code == 201
        ds_id = resp.json()["id"]

        # Set up SpiceDB permissions for the DS
        await grant_ds_permission(spicedb_client, alice_user_id, ds_id, kg_id)

        # Trigger sync
        resp = await async_client.post(
            f"/management/data-sources/{ds_id}/sync",
            headers=tenant_auth_headers,
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["data_source_id"] == ds_id
        assert data["status"] == "pending"
        assert "id" in data
        assert "started_at" in data


class TestGetDataSource:
    """Tests for GET /management/data-sources/{ds_id}."""

    @pytest.mark.asyncio
    async def test_get_data_source_by_id(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test getting a DS by ID returns 200 with correct fields."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)
        kg_id = await _create_kg(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            workspace_id,
            name="KG for get DS",
        )

        # Create DS
        resp = await async_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            headers=tenant_auth_headers,
            json={
                "name": "Get DS Test",
                "adapter_type": "github",
                "connection_config": {"owner": "test", "repo": "test-repo"},
            },
        )
        assert resp.status_code == 201
        ds_id = resp.json()["id"]

        # Set up SpiceDB permissions for the DS
        await grant_ds_permission(spicedb_client, alice_user_id, ds_id, kg_id)

        # Get DS by ID
        resp = await async_client.get(
            f"/management/data-sources/{ds_id}",
            headers=tenant_auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == ds_id
        assert data["name"] == "Get DS Test"
        assert data["adapter_type"] == "github"
        assert data["knowledge_graph_id"] == kg_id
        assert data["has_credentials"] is False
        assert data["schedule_type"] == "manual"


class TestListDataSources:
    """Tests for GET /management/knowledge-graphs/{kg_id}/data-sources."""

    @pytest.mark.asyncio
    async def test_list_data_sources_for_kg(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test listing DSes for a KG returns 200 with pagination."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)
        kg_id = await _create_kg(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            workspace_id,
            name="KG for list DS",
        )

        # Create 2 DSes
        for i in range(2):
            resp = await async_client.post(
                f"/management/knowledge-graphs/{kg_id}/data-sources",
                headers=tenant_auth_headers,
                json={
                    "name": f"List DS {i}",
                    "adapter_type": "github",
                    "connection_config": {"owner": "test", "repo": f"repo-{i}"},
                },
            )
            assert resp.status_code == 201

        # List DSes for KG
        resp = await async_client.get(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            headers=tenant_auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert "offset" in data
        assert "limit" in data


class TestUpdateDataSource:
    """Tests for PATCH /management/data-sources/{ds_id}."""

    @pytest.mark.asyncio
    async def test_update_data_source(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test updating a DS returns 200 with updated name."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)
        kg_id = await _create_kg(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            workspace_id,
            name="KG for update DS",
        )

        # Create DS
        resp = await async_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            headers=tenant_auth_headers,
            json={
                "name": "Original DS",
                "adapter_type": "github",
                "connection_config": {"owner": "test", "repo": "test-repo"},
            },
        )
        assert resp.status_code == 201
        ds_id = resp.json()["id"]

        # Set up SpiceDB permissions for the DS
        await grant_ds_permission(spicedb_client, alice_user_id, ds_id, kg_id)

        # Update DS
        resp = await async_client.patch(
            f"/management/data-sources/{ds_id}",
            headers=tenant_auth_headers,
            json={"name": "Updated Name"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"


class TestDeleteDataSource:
    """Tests for DELETE /management/data-sources/{ds_id}."""

    @pytest.mark.asyncio
    async def test_delete_data_source(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test deleting a DS returns 204 and subsequent GET returns 404."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)
        kg_id = await _create_kg(
            async_client,
            tenant_auth_headers,
            spicedb_client,
            alice_user_id,
            workspace_id,
            name="KG for delete DS",
        )

        # Create DS
        resp = await async_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            headers=tenant_auth_headers,
            json={
                "name": "Delete DS",
                "adapter_type": "github",
                "connection_config": {"owner": "test", "repo": "test-repo"},
            },
        )
        assert resp.status_code == 201
        ds_id = resp.json()["id"]

        # Set up SpiceDB permissions for the DS
        await grant_ds_permission(spicedb_client, alice_user_id, ds_id, kg_id)

        # Delete DS
        resp = await async_client.delete(
            f"/management/data-sources/{ds_id}",
            headers=tenant_auth_headers,
        )
        assert resp.status_code == 204

        # Verify DS is gone
        resp = await async_client.get(
            f"/management/data-sources/{ds_id}",
            headers=tenant_auth_headers,
        )
        assert resp.status_code == 404


class TestDataSourceAuthorization:
    """Tests for authorization enforcement on DS endpoints."""

    @pytest.mark.asyncio
    async def test_unauthorized_user_gets_403(
        self,
        async_client: AsyncClient,
        bob_tenant_auth_headers: dict,
        clean_management_data,
    ):
        """Test that a user without KG edit permission gets 403."""
        resp = await async_client.post(
            "/management/knowledge-graphs/01JFAKEKG0000000000000000000/data-sources",
            headers=bob_tenant_auth_headers,
            json={
                "name": "Unauthorized DS",
                "adapter_type": "github",
                "connection_config": {},
            },
        )

        assert resp.status_code == 403
