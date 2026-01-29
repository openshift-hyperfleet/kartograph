"""Integration tests for TenantRepository.

These tests require PostgreSQL to be running.
They verify the complete flow of persisting and retrieving tenants.
"""

import pytest

from iam.domain.aggregates import Tenant
from iam.infrastructure.tenant_repository import TenantRepository
from iam.ports.exceptions import DuplicateTenantNameError

pytestmark = pytest.mark.integration


class TestTenantRoundTrip:
    """Tests for save and retrieve operations."""

    @pytest.mark.asyncio
    async def test_saves_and_retrieves_tenant(
        self, tenant_repository: TenantRepository, async_session, clean_iam_data
    ):
        """Should save tenant to PostgreSQL and retrieve it."""
        tenant = Tenant.create(name="Acme Corp")

        async with async_session.begin():
            await tenant_repository.save(tenant)

        # Retrieve the tenant
        retrieved = await tenant_repository.get_by_id(tenant.id)

        assert retrieved is not None
        assert retrieved.id.value == tenant.id.value
        assert retrieved.name == tenant.name


class TestTenantDeletion:
    """Tests for deleting tenants."""

    @pytest.mark.asyncio
    async def test_deletes_tenant(
        self, tenant_repository: TenantRepository, async_session, clean_iam_data
    ):
        """Should delete tenant from PostgreSQL."""
        tenant = Tenant.create(name="Acme Corp")

        # Save tenant
        async with async_session.begin():
            await tenant_repository.save(tenant)

        # Verify it exists, then delete in same transaction
        async with async_session.begin():
            retrieved = await tenant_repository.get_by_id(tenant.id)
            assert retrieved is not None

            # Mark for deletion and delete
            retrieved.mark_for_deletion(members=[])  # Empty tenant, no members
            result = await tenant_repository.delete(retrieved)

        assert result is True

        # Verify it's gone
        deleted = await tenant_repository.get_by_id(tenant.id)
        assert deleted is None


class TestTenantUniqueness:
    """Tests for tenant name uniqueness constraints."""

    @pytest.mark.asyncio
    async def test_duplicate_name_raises_error(
        self, tenant_repository: TenantRepository, async_session, clean_iam_data
    ):
        """Should raise DuplicateTenantNameError for duplicate name."""
        tenant1 = Tenant.create(name="Acme Corp")

        # Save first tenant
        async with async_session.begin():
            await tenant_repository.save(tenant1)

        # Try to save another tenant with same name
        tenant2 = Tenant.create(name="Acme Corp")

        with pytest.raises(DuplicateTenantNameError):
            async with async_session.begin():
                await tenant_repository.save(tenant2)


class TestGetByName:
    """Tests for retrieving tenants by name."""

    @pytest.mark.asyncio
    async def test_retrieves_tenant_by_name(
        self, tenant_repository: TenantRepository, async_session, clean_iam_data
    ):
        """Should retrieve tenant by name."""
        tenant = Tenant.create(name="Acme Corp")

        async with async_session.begin():
            await tenant_repository.save(tenant)

        # Retrieve by name
        retrieved = await tenant_repository.get_by_name("Acme Corp")

        assert retrieved is not None
        assert retrieved.id.value == tenant.id.value
        assert retrieved.name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_name(
        self, tenant_repository: TenantRepository, clean_iam_data
    ):
        """Should return None when tenant name doesn't exist."""
        retrieved = await tenant_repository.get_by_name("Nonexistent")

        assert retrieved is None


class TestListAll:
    """Tests for listing all tenants."""

    @pytest.mark.asyncio
    async def test_lists_all_tenants(
        self, tenant_repository: TenantRepository, async_session, clean_iam_data
    ):
        """Should list all tenants in the system."""
        tenant1 = Tenant.create(name="Acme Corp")
        tenant2 = Tenant.create(name="Wayne Enterprises")
        tenant3 = Tenant.create(name="Stark Industries")

        async with async_session.begin():
            await tenant_repository.save(tenant1)
            await tenant_repository.save(tenant2)
            await tenant_repository.save(tenant3)

        # List all tenants
        all_tenants = await tenant_repository.list_all()

        # Should have 4 tenants: 3 created + 1 default tenant
        assert len(all_tenants) == 4
        tenant_ids = {t.id.value for t in all_tenants}
        assert tenant1.id.value in tenant_ids
        assert tenant2.id.value in tenant_ids
        assert tenant3.id.value in tenant_ids

    @pytest.mark.asyncio
    async def test_includes_default_tenant(
        self, tenant_repository: TenantRepository, clean_iam_data
    ):
        """Should include the default tenant created at app startup."""
        tenants = await tenant_repository.list_all()

        # Default tenant should exist
        assert len(tenants) == 1
        assert tenants[0].name == "default"
