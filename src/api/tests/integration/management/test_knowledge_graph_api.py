"""Integration tests for Knowledge Graph API endpoints.

Tests the full stack: HTTP request -> route -> DI -> service ->
SpiceDB + PostgreSQL -> response.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from shared_kernel.authorization.protocols import AuthorizationProvider
from tests.integration.management.conftest import grant_kg_permission

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


class TestKnowledgeGraphCreation:
    """Tests for POST /management/workspaces/{workspace_id}/knowledge-graphs."""

    @pytest.mark.asyncio
    async def test_creates_knowledge_graph(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        clean_management_data,
    ):
        """Test creating a KG via API returns 201 with correct fields."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)

        resp = await async_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            headers=tenant_auth_headers,
            json={"name": "Test KG", "description": "Integration test KG"},
        )

        assert resp.status_code == 201, f"Unexpected: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["name"] == "Test KG"
        assert data["description"] == "Integration test KG"
        assert data["workspace_id"] == workspace_id
        assert "id" in data
        assert "tenant_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_duplicate_name_returns_409(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        clean_management_data,
    ):
        """Test that creating a KG with duplicate name returns 409."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)

        # Create first KG
        resp = await async_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            headers=tenant_auth_headers,
            json={"name": "Unique KG"},
        )
        assert resp.status_code == 201

        # Attempt duplicate
        resp = await async_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            headers=tenant_auth_headers,
            json={"name": "Unique KG"},
        )
        assert resp.status_code == 409


class TestKnowledgeGraphList:
    """Tests for GET /management/workspaces/{workspace_id}/knowledge-graphs."""

    @pytest.mark.asyncio
    async def test_lists_knowledge_graphs_with_pagination(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test listing KGs with pagination."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)

        # Create 3 KGs
        kg_ids = []
        for i in range(3):
            resp = await async_client.post(
                f"/management/workspaces/{workspace_id}/knowledge-graphs",
                headers=tenant_auth_headers,
                json={"name": f"KG {i}"},
            )
            assert resp.status_code == 201
            kg_id = resp.json()["id"]
            kg_ids.append(kg_id)

            # Set up SpiceDB relationships for listing
            await grant_kg_permission(
                spicedb_client, alice_user_id, kg_id, workspace_id
            )

        # List with pagination
        resp = await async_client.get(
            f"/management/workspaces/{workspace_id}/knowledge-graphs?offset=0&limit=2",
            headers=tenant_auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["offset"] == 0
        assert data["limit"] == 2


class TestKnowledgeGraphGet:
    """Tests for GET /management/knowledge-graphs/{kg_id}."""

    @pytest.mark.asyncio
    async def test_gets_knowledge_graph(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test getting a KG by ID returns 200."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)

        # Create KG
        resp = await async_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            headers=tenant_auth_headers,
            json={"name": "Get Test KG"},
        )
        assert resp.status_code == 201
        kg_id = resp.json()["id"]

        # Grant SpiceDB permissions
        await grant_kg_permission(spicedb_client, alice_user_id, kg_id, workspace_id)

        # Get KG
        resp = await async_client.get(
            f"/management/knowledge-graphs/{kg_id}",
            headers=tenant_auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == kg_id
        assert data["name"] == "Get Test KG"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        clean_management_data,
    ):
        """Test getting a nonexistent KG returns 404."""
        resp = await async_client.get(
            "/management/knowledge-graphs/01JNONEXISTENT000000000000",
            headers=tenant_auth_headers,
        )

        assert resp.status_code == 404


class TestKnowledgeGraphUpdate:
    """Tests for PATCH /management/knowledge-graphs/{kg_id}."""

    @pytest.mark.asyncio
    async def test_updates_knowledge_graph(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test updating a KG returns 200 with updated data."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)

        # Create KG
        resp = await async_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            headers=tenant_auth_headers,
            json={"name": "Original Name"},
        )
        assert resp.status_code == 201
        kg_id = resp.json()["id"]

        # Grant SpiceDB permissions
        await grant_kg_permission(spicedb_client, alice_user_id, kg_id, workspace_id)

        # Update KG
        resp = await async_client.patch(
            f"/management/knowledge-graphs/{kg_id}",
            headers=tenant_auth_headers,
            json={"name": "Updated Name"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"


class TestKnowledgeGraphDelete:
    """Tests for DELETE /management/knowledge-graphs/{kg_id}."""

    @pytest.mark.asyncio
    async def test_deletes_knowledge_graph(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict,
        spicedb_client: AuthorizationProvider,
        alice_user_id: str,
        clean_management_data,
    ):
        """Test deleting a KG returns 204."""
        workspace_id = await _get_root_workspace_id(async_client, tenant_auth_headers)

        # Create KG
        resp = await async_client.post(
            f"/management/workspaces/{workspace_id}/knowledge-graphs",
            headers=tenant_auth_headers,
            json={"name": "Delete Test KG"},
        )
        assert resp.status_code == 201
        kg_id = resp.json()["id"]

        # Grant SpiceDB permissions (need manage for delete)
        await grant_kg_permission(spicedb_client, alice_user_id, kg_id, workspace_id)

        # Delete KG
        resp = await async_client.delete(
            f"/management/knowledge-graphs/{kg_id}",
            headers=tenant_auth_headers,
        )

        assert resp.status_code == 204

        # Verify it's gone
        resp = await async_client.get(
            f"/management/knowledge-graphs/{kg_id}",
            headers=tenant_auth_headers,
        )
        assert resp.status_code == 404


class TestKnowledgeGraphAuthorization:
    """Tests for authorization enforcement on KG endpoints."""

    @pytest.mark.asyncio
    async def test_unauthorized_user_gets_403(
        self,
        async_client: AsyncClient,
        bob_tenant_auth_headers: dict,
        clean_management_data,
    ):
        """Test that a user without workspace edit permission gets 403."""
        # Bob has tenant membership but no workspace admin/edit
        resp = await async_client.post(
            "/management/workspaces/01JFAKEWORKSPACE00000000000/knowledge-graphs",
            headers=bob_tenant_auth_headers,
            json={"name": "Unauthorized KG"},
        )

        assert resp.status_code == 403
