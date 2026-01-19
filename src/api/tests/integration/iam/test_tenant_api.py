"""Integration tests for Tenant API endpoints.

Tests the full vertical slice: API → Service → Repository → PostgreSQL.
"""

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from iam.domain.value_objects import TenantId, UserId
from main import app

pytestmark = pytest.mark.integration


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


class TestCreateTenant:
    """Tests for POST /iam/tenants endpoint."""

    @pytest.mark.asyncio
    async def test_creates_tenant_successfully(self, async_client, clean_iam_data):
        """Should create tenant and return 201 with tenant details."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()

        response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers={
                "X-User-Id": user_id.value,
                "X-Username": "admin",
                "X-Tenant-Id": tenant_id.value,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Acme Corp"
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_returns_409_for_duplicate_name(self, async_client, clean_iam_data):
        """Should return 409 Conflict if tenant name already exists."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()
        headers = {
            "X-User-Id": user_id.value,
            "X-Username": "admin",
            "X-Tenant-Id": tenant_id.value,
        }

        # Create first tenant
        await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=headers,
        )

        # Try to create duplicate
        response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=headers,
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_400_for_empty_name(self, async_client, clean_iam_data):
        """Should return 400 for empty tenant name."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()

        response = await async_client.post(
            "/iam/tenants",
            json={"name": ""},
            headers={
                "X-User-Id": user_id.value,
                "X-Username": "admin",
                "X-Tenant-Id": tenant_id.value,
            },
        )

        assert response.status_code == 422


class TestGetTenant:
    """Tests for GET /iam/tenants/:id endpoint."""

    @pytest.mark.asyncio
    async def test_gets_tenant_successfully(self, async_client, clean_iam_data):
        """Should retrieve tenant by ID."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()
        headers = {
            "X-User-Id": user_id.value,
            "X-Username": "admin",
            "X-Tenant-Id": tenant_id.value,
        }

        # Create tenant
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=headers,
        )
        created_tenant_id = create_response.json()["id"]

        # Get tenant
        response = await async_client.get(
            f"/iam/tenants/{created_tenant_id}", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_tenant_id
        assert data["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_tenant(self, async_client):
        """Should return 404 if tenant doesn't exist."""
        headers = {
            "X-User-Id": UserId.generate().value,
            "X-Username": "admin",
            "X-Tenant-Id": TenantId.generate().value,
        }

        response = await async_client.get(
            f"/iam/tenants/{TenantId.generate().value}",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_tenant_id(
        self, async_client, clean_iam_data
    ):
        """Should return 400 for invalid tenant ID format."""
        headers = {
            "X-User-Id": UserId.generate().value,
            "X-Username": "admin",
            "X-Tenant-Id": TenantId.generate().value,
        }

        response = await async_client.get("/iam/tenants/invalid", headers=headers)

        assert response.status_code == 400


class TestListTenants:
    """Tests for GET /iam/tenants endpoint."""

    @pytest.mark.asyncio
    async def test_lists_all_tenants(self, async_client, clean_iam_data):
        """Should list all tenants in the system."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()
        headers = {
            "X-User-Id": user_id.value,
            "X-Username": "admin",
            "X-Tenant-Id": tenant_id.value,
        }

        # Create multiple tenants
        await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=headers,
        )
        await async_client.post(
            "/iam/tenants",
            json={"name": "Wayne Enterprises"},
            headers=headers,
        )
        await async_client.post(
            "/iam/tenants",
            json={"name": "Stark Industries"},
            headers=headers,
        )

        # List all tenants
        response = await async_client.get("/iam/tenants", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        tenant_names = {t["name"] for t in data}
        assert "Acme Corp" in tenant_names
        assert "Wayne Enterprises" in tenant_names
        assert "Stark Industries" in tenant_names

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_tenants(
        self, async_client, clean_iam_data
    ):
        """Should return empty list when no tenants exist."""
        headers = {
            "X-User-Id": UserId.generate().value,
            "X-Username": "admin",
            "X-Tenant-Id": TenantId.generate().value,
        }

        response = await async_client.get("/iam/tenants", headers=headers)

        assert response.status_code == 200
        assert response.json() == []


class TestDeleteTenant:
    """Tests for DELETE /iam/tenants/:id endpoint."""

    @pytest.mark.asyncio
    async def test_deletes_tenant_successfully(self, async_client, clean_iam_data):
        """Should delete tenant and return 204."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()
        headers = {
            "X-User-Id": user_id.value,
            "X-Username": "admin",
            "X-Tenant-Id": tenant_id.value,
        }

        # Create tenant
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=headers,
        )
        created_tenant_id = create_response.json()["id"]

        # Delete tenant
        response = await async_client.delete(
            f"/iam/tenants/{created_tenant_id}",
            headers=headers,
        )

        assert response.status_code == 204

        # Verify it's gone
        get_response = await async_client.get(
            f"/iam/tenants/{created_tenant_id}", headers=headers
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_tenant(self, async_client):
        """Should return 404 if tenant doesn't exist."""
        headers = {
            "X-User-Id": UserId.generate().value,
            "X-Username": "admin",
            "X-Tenant-Id": TenantId.generate().value,
        }

        response = await async_client.delete(
            f"/iam/tenants/{TenantId.generate().value}",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_id(self, async_client, clean_iam_data):
        """Should return 400 for invalid tenant ID."""
        headers = {
            "X-User-Id": UserId.generate().value,
            "X-Username": "admin",
            "X-Tenant-Id": TenantId.generate().value,
        }

        response = await async_client.delete(
            "/iam/tenants/invalid",
            headers=headers,
        )

        assert response.status_code == 400
