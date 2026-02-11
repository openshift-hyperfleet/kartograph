"""Integration tests for Tenant API endpoints.

Tests the full vertical slice: API -> Service -> Repository -> PostgreSQL.
Uses JWT Bearer token authentication via Keycloak.
"""

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from iam.domain.value_objects import TenantId
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


class TestCreateTenant:
    """Tests for POST /iam/tenants endpoint."""

    @pytest.mark.asyncio
    async def test_creates_tenant_successfully(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should create tenant and return 201 with tenant details."""
        response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Acme Corp"
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_returns_409_for_duplicate_name(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 409 Conflict if tenant name already exists."""
        # Create first tenant
        await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )

        # Try to create duplicate
        response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_422_for_empty_name(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 422 for empty tenant name."""
        response = await async_client.post(
            "/iam/tenants",
            json={"name": ""},
            headers=tenant_auth_headers,
        )

        assert response.status_code == 422


class TestGetTenant:
    """Tests for GET /iam/tenants/:id endpoint."""

    @pytest.mark.asyncio
    async def test_gets_tenant_successfully(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should retrieve tenant by ID."""
        # Create tenant
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        created_tenant_id = create_response.json()["id"]

        # Get tenant
        response = await async_client.get(
            f"/iam/tenants/{created_tenant_id}", headers=tenant_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_tenant_id
        assert data["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_tenant(
        self, async_client, tenant_auth_headers
    ):
        """Should return 404 if tenant doesn't exist."""
        response = await async_client.get(
            f"/iam/tenants/{TenantId.generate().value}",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_tenant_id(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 400 for invalid tenant ID format."""
        response = await async_client.get(
            "/iam/tenants/invalid", headers=tenant_auth_headers
        )

        assert response.status_code == 400


class TestListTenants:
    """Tests for GET /iam/tenants endpoint."""

    @pytest.mark.asyncio
    async def test_lists_all_tenants(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should list all tenants in the system."""
        # Create multiple tenants
        await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        await async_client.post(
            "/iam/tenants",
            json={"name": "Wayne Enterprises"},
            headers=tenant_auth_headers,
        )
        await async_client.post(
            "/iam/tenants",
            json={"name": "Stark Industries"},
            headers=tenant_auth_headers,
        )

        # List all tenants
        response = await async_client.get("/iam/tenants", headers=tenant_auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should have 4 tenants: 3 created + 1 default tenant
        assert len(data) == 4
        tenant_names = {t["name"] for t in data}
        assert "Acme Corp" in tenant_names
        assert "Wayne Enterprises" in tenant_names
        assert "Stark Industries" in tenant_names

        # Verify default tenant is included (from settings, not hardcoded)
        from infrastructure.settings import get_iam_settings

        assert get_iam_settings().default_tenant_name in tenant_names

    @pytest.mark.asyncio
    async def test_includes_default_tenant(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should include the default tenant created at app startup."""
        from infrastructure.settings import get_iam_settings

        response = await async_client.get("/iam/tenants", headers=tenant_auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should have exactly 1 tenant (the default)
        assert len(data) == 1
        assert data[0]["name"] == get_iam_settings().default_tenant_name


class TestDeleteTenant:
    """Tests for DELETE /iam/tenants/:id endpoint."""

    @pytest.mark.asyncio
    async def test_deletes_tenant_successfully(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should delete tenant and return 204."""
        # Create tenant
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        created_tenant_id = create_response.json()["id"]

        # Delete tenant
        response = await async_client.delete(
            f"/iam/tenants/{created_tenant_id}",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 204

        # Verify it's gone
        get_response = await async_client.get(
            f"/iam/tenants/{created_tenant_id}", headers=tenant_auth_headers
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_tenant(
        self, async_client, tenant_auth_headers
    ):
        """Should return 404 if tenant doesn't exist."""
        response = await async_client.delete(
            f"/iam/tenants/{TenantId.generate().value}",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_id(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 400 for invalid tenant ID."""
        response = await async_client.delete(
            "/iam/tenants/invalid",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 400
