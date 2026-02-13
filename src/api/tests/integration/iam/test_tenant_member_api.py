"""Integration tests for Tenant Member API endpoints.

Tests the full vertical slice: API -> Service -> Repository -> PostgreSQL + SpiceDB.
Uses JWT Bearer token authentication via Keycloak.
"""

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from iam.dependencies.multi_tenant_mode import _get_single_tenant_mode
from iam.domain.value_objects import TenantId, TenantRole, UserId
from main import app
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
)
from tests.integration.iam.conftest import wait_for_permission

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support.

    Uses LifespanManager to ensure app lifespan (database engine init)
    runs before tests and cleanup runs after.

    Overrides _get_single_tenant_mode to return False so that tenant
    CRUD routes (POST, DELETE) are not blocked by the single-tenant gate.
    """
    app.dependency_overrides[_get_single_tenant_mode] = lambda: False
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    app.dependency_overrides.pop(_get_single_tenant_mode, None)


class TestAddTenantMember:
    """Tests for POST /iam/tenants/{tenant_id}/members endpoint."""

    @pytest.mark.asyncio
    async def test_adds_admin_member_successfully(
        self,
        async_client,
        clean_iam_data,
        tenant_auth_headers,
        spicedb_client,
        alice_user_id,
    ):
        """Should add an admin member to tenant and return 201."""
        # Create tenant first
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        assert create_response.status_code == 201
        tenant_id = create_response.json()["id"]

        # Give alice admin permission on the tenant
        # alice_user_id is the actual Keycloak UUID from JWT 'sub' claim
        resource = format_resource(ResourceType.TENANT, tenant_id)
        subject = format_resource(ResourceType.USER, alice_user_id)

        await spicedb_client.write_relationship(
            resource=resource,
            relation=TenantRole.ADMIN.value,
            subject=subject,
        )

        # Wait for permission to propagate
        permission_ready = await wait_for_permission(
            spicedb_client,
            resource=resource,
            permission=Permission.ADMINISTRATE,
            subject=subject,
            timeout=5.0,
        )
        assert permission_ready, "Timed out waiting for admin permission"

        # Now add a new user as admin
        new_user_id = UserId.generate().value
        response = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": new_user_id, "role": "admin"},
            headers=tenant_auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == new_user_id
        assert data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_adds_regular_member_successfully(
        self,
        async_client,
        clean_iam_data,
        tenant_auth_headers,
        spicedb_client,
        alice_user_id,
    ):
        """Should add a regular member to tenant and return 201."""
        # Create tenant
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        tenant_id = create_response.json()["id"]

        # Set up alice as admin via SpiceDB
        resource = format_resource(ResourceType.TENANT, tenant_id)
        subject = format_resource(ResourceType.USER, alice_user_id)

        await spicedb_client.write_relationship(
            resource=resource,
            relation=TenantRole.ADMIN.value,
            subject=subject,
        )

        # Wait for permission to propagate
        permission_ready = await wait_for_permission(
            spicedb_client,
            resource=resource,
            permission=Permission.ADMINISTRATE,
            subject=subject,
            timeout=5.0,
        )
        assert permission_ready, "Timed out waiting for admin permission"

        # Add member
        new_user_id = UserId.generate().value
        response = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": new_user_id, "role": "member"},
            headers=tenant_auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == new_user_id
        assert data["role"] == "member"

    @pytest.mark.asyncio
    async def test_returns_403_when_not_authorized(
        self, async_client, clean_iam_data, tenant_auth_headers, bob_tenant_auth_headers
    ):
        """Should return 403 if caller is not tenant admin."""
        # Alice creates tenant (she becomes admin automatically)
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        tenant_id = create_response.json()["id"]

        # Bob tries to add member (he is NOT admin on this tenant)
        response = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": UserId.generate().value, "role": "member"},
            headers=bob_tenant_auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_403_for_nonexistent_tenant(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 403 if tenant doesn't exist to avoid leaking existence."""
        fake_tenant_id = TenantId.generate().value
        response = await async_client.post(
            f"/iam/tenants/{fake_tenant_id}/members",
            json={"user_id": UserId.generate().value, "role": "member"},
            headers=tenant_auth_headers,
        )

        # 403 is returned to avoid leaking existence
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_tenant_id(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 400 for invalid tenant ID format."""
        response = await async_client.post(
            "/iam/tenants/invalid/members",
            json={"user_id": UserId.generate().value, "role": "member"},
            headers=tenant_auth_headers,
        )

        assert response.status_code == 400


class TestRemoveTenantMember:
    """Tests for DELETE /iam/tenants/{tenant_id}/members/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_removes_member_successfully(
        self,
        async_client,
        clean_iam_data,
        tenant_auth_headers,
        spicedb_client,
        alice_user_id,
    ):
        """Should remove member from tenant and return 204."""
        # Create tenant
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        tenant_id = create_response.json()["id"]

        # Set up alice as admin
        resource = format_resource(ResourceType.TENANT, tenant_id)
        subject = format_resource(ResourceType.USER, alice_user_id)

        await spicedb_client.write_relationship(
            resource=resource,
            relation=TenantRole.ADMIN.value,
            subject=subject,
        )

        permission_ready = await wait_for_permission(
            spicedb_client,
            resource=resource,
            permission=Permission.ADMINISTRATE,
            subject=subject,
            timeout=5.0,
        )
        assert permission_ready, "Timed out waiting for admin permission"

        # Add a member to remove
        member_user_id = UserId.generate().value
        add_response = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": member_user_id, "role": "member"},
            headers=tenant_auth_headers,
        )
        assert add_response.status_code == 201

        # Wait for member relationship to propagate
        member_ready = await wait_for_permission(
            spicedb_client,
            resource=resource,
            permission=Permission.VIEW,
            subject=format_resource(ResourceType.USER, member_user_id),
            timeout=5.0,
        )
        assert member_ready, "Timed out waiting for member permission"

        # Remove the member
        response = await async_client.delete(
            f"/iam/tenants/{tenant_id}/members/{member_user_id}",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_returns_409_when_removing_last_admin(
        self,
        async_client,
        clean_iam_data,
        tenant_auth_headers,
        spicedb_client,
        alice_user_id,
    ):
        """Should return 409 if trying to remove the last admin."""
        # Create tenant
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        tenant_id = create_response.json()["id"]

        # Set up alice as the only admin
        resource = format_resource(ResourceType.TENANT, tenant_id)
        subject = format_resource(ResourceType.USER, alice_user_id)

        await spicedb_client.write_relationship(
            resource=resource,
            relation=TenantRole.ADMIN.value,
            subject=subject,
        )

        permission_ready = await wait_for_permission(
            spicedb_client,
            resource=resource,
            permission=Permission.ADMINISTRATE,
            subject=subject,
            timeout=5.0,
        )
        assert permission_ready, "Timed out waiting for admin permission"

        # Try to remove alice (the only admin)
        response = await async_client.delete(
            f"/iam/tenants/{tenant_id}/members/{alice_user_id}",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_returns_403_when_not_authorized(
        self, async_client, clean_iam_data, tenant_auth_headers, bob_tenant_auth_headers
    ):
        """Should return 403 if caller is not tenant admin."""
        # Alice creates tenant (she becomes admin automatically)
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        tenant_id = create_response.json()["id"]

        # Bob tries to remove member (he is NOT admin on this tenant)
        response = await async_client.delete(
            f"/iam/tenants/{tenant_id}/members/{UserId.generate().value}",
            headers=bob_tenant_auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_tenant_id(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 400 for invalid tenant ID format."""
        response = await async_client.delete(
            f"/iam/tenants/invalid/members/{UserId.generate().value}",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 400


class TestListTenantMembers:
    """Tests for GET /iam/tenants/{tenant_id}/members endpoint."""

    @pytest.mark.asyncio
    async def test_lists_members_successfully(
        self,
        async_client,
        clean_iam_data,
        tenant_auth_headers,
        spicedb_client,
        alice_user_id,
    ):
        """Should list all tenant members."""
        # Create tenant
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        tenant_id = create_response.json()["id"]

        # Set up alice as admin
        resource = format_resource(ResourceType.TENANT, tenant_id)
        subject = format_resource(ResourceType.USER, alice_user_id)

        await spicedb_client.write_relationship(
            resource=resource,
            relation=TenantRole.ADMIN.value,
            subject=subject,
        )

        admin_ready = await wait_for_permission(
            spicedb_client,
            resource=resource,
            permission=Permission.ADMINISTRATE,
            subject=subject,
            timeout=5.0,
        )
        assert admin_ready, "Timed out waiting for admin permission"

        # Add another member
        member_user_id = UserId.generate().value
        add_member_response = await async_client.post(
            f"/iam/tenants/{tenant_id}/members",
            json={"user_id": member_user_id, "role": "member"},
            headers=tenant_auth_headers,
        )
        assert add_member_response.status_code == 201, (
            f"Failed to add member: {add_member_response.status_code} - {add_member_response.text}"
        )

        # Wait for the member to be added to SpiceDB
        member_ready = await wait_for_permission(
            spicedb_client,
            resource=resource,
            permission=Permission.VIEW,  # members have view permission
            subject=format_resource(ResourceType.USER, member_user_id),
            timeout=5.0,
        )
        assert member_ready, "Timed out waiting for member permission"

        # List members
        response = await async_client.get(
            f"/iam/tenants/{tenant_id}/members",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have alice as admin and the new member
        user_ids = {m["user_id"] for m in data}
        assert alice_user_id in user_ids
        assert member_user_id in user_ids

    @pytest.mark.asyncio
    async def test_returns_403_when_not_authorized(
        self, async_client, clean_iam_data, tenant_auth_headers, bob_tenant_auth_headers
    ):
        """Should return 403 if caller is not tenant admin."""
        # Alice creates tenant (she becomes admin automatically)
        create_response = await async_client.post(
            "/iam/tenants",
            json={"name": "Acme Corp"},
            headers=tenant_auth_headers,
        )
        tenant_id = create_response.json()["id"]

        # Bob tries to list members (he is NOT admin on this tenant)
        response = await async_client.get(
            f"/iam/tenants/{tenant_id}/members",
            headers=bob_tenant_auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_403_for_nonexistent_tenant(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 403 if tenant doesn't exist to avoid leaking existence."""
        fake_tenant_id = TenantId.generate().value
        response = await async_client.get(
            f"/iam/tenants/{fake_tenant_id}/members",
            headers=tenant_auth_headers,
        )

        # 403 to avoid leaking existence
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_tenant_id(
        self, async_client, clean_iam_data, tenant_auth_headers
    ):
        """Should return 400 for invalid tenant ID format."""
        response = await async_client.get(
            "/iam/tenants/invalid/members",
            headers=tenant_auth_headers,
        )

        assert response.status_code == 400
