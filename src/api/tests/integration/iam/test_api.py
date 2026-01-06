"""Integration tests for IAM API endpoints.

Tests the full vertical slice: API → Service → Repository → PostgreSQL + SpiceDB.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from iam.domain.value_objects import GroupId, TenantId, UserId
from main import app

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestCreateGroup:
    """Tests for POST /iam/groups endpoint."""

    @pytest.mark.asyncio
    async def test_creates_group_successfully(self, async_client, clean_iam_data):
        """Should create group and return 201 with group details."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()

        response = await async_client.post(
            "/iam/groups",
            json={"name": "Engineering"},
            headers={
                "X-User-Id": user_id.value,
                "X-Username": "alice",
                "X-Tenant-Id": tenant_id.value,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Engineering"
        assert data["id"] is not None
        assert len(data["members"]) == 1
        assert data["members"][0]["user_id"] == user_id.value
        assert data["members"][0]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_returns_409_for_duplicate_name(self, async_client, clean_iam_data):
        """Should return 409 Conflict if group name exists in tenant."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()
        headers = {
            "X-User-Id": user_id.value,
            "X-Username": "alice",
            "X-Tenant-Id": tenant_id.value,
        }

        # Create first group
        await async_client.post(
            "/iam/groups",
            json={"name": "Engineering"},
            headers=headers,
        )

        # Try to create duplicate
        response = await async_client.post(
            "/iam/groups",
            json={"name": "Engineering"},
            headers=headers,
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_allows_same_name_in_different_tenants(
        self, async_client, clean_iam_data
    ):
        """Should allow same group name in different tenants."""
        user_id = UserId.generate()
        tenant1 = TenantId.generate()
        tenant2 = TenantId.generate()

        # Create in tenant 1
        response1 = await async_client.post(
            "/iam/groups",
            json={"name": "Engineering"},
            headers={
                "X-User-Id": user_id.value,
                "X-Username": "alice",
                "X-Tenant-Id": tenant1.value,
            },
        )
        assert response1.status_code == 201

        # Create same name in tenant 2
        response2 = await async_client.post(
            "/iam/groups",
            json={"name": "Engineering"},
            headers={
                "X-User-Id": user_id.value,
                "X-Username": "alice",
                "X-Tenant-Id": tenant2.value,
            },
        )
        assert response2.status_code == 201

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_tenant_id(self, async_client):
        """Should return 400 for invalid tenant ID format."""
        response = await async_client.post(
            "/iam/groups",
            json={"name": "Engineering"},
            headers={
                "X-User-Id": UserId.generate().value,
                "X-Username": "alice",
                "X-Tenant-Id": "invalid",
            },
        )

        assert response.status_code == 400
        assert "Invalid ID format" in response.json()["detail"]


class TestGetGroup:
    """Tests for GET /iam/groups/:id endpoint."""

    @pytest.mark.asyncio
    async def test_gets_group_successfully(self, async_client, clean_iam_data):
        """Should retrieve group with members."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()
        headers = {
            "X-User-Id": user_id.value,
            "X-Username": "alice",
            "X-Tenant-Id": tenant_id.value,
        }

        # Create group
        create_response = await async_client.post(
            "/iam/groups",
            json={"name": "Engineering"},
            headers=headers,
        )
        group_id = create_response.json()["id"]

        # Get group
        response = await async_client.get(f"/iam/groups/{group_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == group_id
        assert data["name"] == "Engineering"
        assert len(data["members"]) == 1

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_group(self, async_client):
        """Should return 404 if group doesn't exist."""
        response = await async_client.get(f"/iam/groups/{GroupId.generate().value}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_group_id(self, async_client):
        """Should return 400 for invalid group ID format."""
        response = await async_client.get("/iam/groups/invalid")

        assert response.status_code == 400


class TestDeleteGroup:
    """Tests for DELETE /iam/groups/:id endpoint."""

    @pytest.mark.asyncio
    async def test_deletes_group_successfully(self, async_client, clean_iam_data):
        """Should delete group and return 204."""
        user_id = UserId.generate()
        tenant_id = TenantId.generate()
        headers = {
            "X-User-Id": user_id.value,
            "X-Username": "alice",
            "X-Tenant-Id": tenant_id.value,
        }

        # Create group
        create_response = await async_client.post(
            "/iam/groups",
            json={"name": "Engineering"},
            headers=headers,
        )
        group_id = create_response.json()["id"]

        # Delete group
        response = await async_client.delete(
            f"/iam/groups/{group_id}",
            headers=headers,
        )

        assert response.status_code == 204

        # Verify it's gone
        get_response = await async_client.get(f"/iam/groups/{group_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_group(self, async_client):
        """Should return 404 if group doesn't exist."""
        headers = {
            "X-User-Id": UserId.generate().value,
            "X-Username": "alice",
            "X-Tenant-Id": TenantId.generate().value,
        }

        response = await async_client.delete(
            f"/iam/groups/{GroupId.generate().value}",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_id(self, async_client):
        """Should return 400 for invalid group ID."""
        headers = {
            "X-User-Id": UserId.generate().value,
            "X-Username": "alice",
            "X-Tenant-Id": TenantId.generate().value,
        }

        response = await async_client.delete(
            "/iam/groups/invalid",
            headers=headers,
        )

        assert response.status_code == 400
