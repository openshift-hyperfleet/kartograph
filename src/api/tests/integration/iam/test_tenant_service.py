"""Service-level rollback integration tests for TenantService.

These tests verify that tenant deletion is atomic: if the database
transaction fails at any point inside TenantService.delete_tenant(), the
tenant record (and its cascade targets) is NOT deleted (no partial state).

TenantService.delete_tenant() wraps the entire cascade inside
``async with self._session.begin()``. Only a real-database integration
test (with a real AsyncSession) can verify this transaction boundary
rolls back correctly on failure. Mock sessions cannot test SQLAlchemy
rollback semantics.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.services.tenant_service import TenantService
from iam.domain.aggregates import Tenant
from iam.domain.value_objects import UserId
from iam.infrastructure.api_key_repository import APIKeyRepository
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.tenant_repository import TenantRepository
from iam.infrastructure.workspace_repository import WorkspaceRepository
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.types import (
    ResourceType,
    format_resource,
    format_subject,
)
from tests.fakes.authorization import InMemoryAuthorizationProvider

pytestmark = pytest.mark.integration


class TestTenantServiceDeleteRollback:
    """Tests that TenantService.delete_tenant() rolls back fully on failure.

    TenantService.delete_tenant() wraps the delete cascade inside
    ``async with self._session.begin()``. If an exception escapes that block,
    SQLAlchemy must roll back the entire unit of work. These tests confirm
    that invariant holds at the real-database level.
    """

    @pytest.mark.asyncio
    async def test_tenant_deletion_rollback_on_failure(
        self,
        async_session: AsyncSession,
        clean_iam_data: None,
    ) -> None:
        """When tenant deletion fails mid-transaction, the tenant is not deleted.

        Creates a tenant, starts a TenantService.delete_tenant() cascade,
        injects a failure at the final deletion step, and asserts the tenant
        still exists afterwards — verifying full transactional rollback.
        """
        admin_user_id = UserId.from_string("admin-test-rollback")
        outbox_repo = OutboxRepository(async_session)
        fake_authz = InMemoryAuthorizationProvider()

        tenant_repo = TenantRepository(
            session=async_session,
            outbox=outbox_repo,
        )
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=fake_authz,
            outbox=outbox_repo,
        )
        group_repo = GroupRepository(
            session=async_session,
            authz=fake_authz,
            outbox=outbox_repo,
        )
        api_key_repo = APIKeyRepository(
            session=async_session,
            outbox=outbox_repo,
        )

        # Arrange: create a tenant to delete
        tenant = Tenant.create(name="Rollback Test Tenant")
        async with async_session.begin():
            await tenant_repo.save(tenant)

        # Grant the admin user administrate permission on the tenant
        await fake_authz.write_relationship(
            resource=format_resource(ResourceType.TENANT, tenant.id.value),
            relation="admin",
            subject=format_subject(ResourceType.USER, admin_user_id.value),
        )

        # Instantiate TenantService with real session (tests actual transaction semantics)
        service = TenantService(
            tenant_repository=tenant_repo,
            workspace_repository=workspace_repo,
            group_repository=group_repo,
            api_key_repository=api_key_repo,
            authz=fake_authz,
            session=async_session,
        )

        # Patch tenant_repo.delete to inject failure inside the service's transaction
        original_delete = tenant_repo.delete

        async def _failing_delete(t: Tenant) -> bool:
            raise Exception("Simulated failure mid-tenant-deletion")

        tenant_repo.delete = _failing_delete  # type: ignore[assignment]

        try:
            # Act: the service delete must raise (failure injected mid-cascade)
            with pytest.raises(Exception, match="Simulated failure"):
                await service.delete_tenant(
                    tenant_id=tenant.id,
                    requesting_user_id=admin_user_id,
                )
        finally:
            tenant_repo.delete = original_delete  # type: ignore[assignment]

        # Assert: tenant still exists — the transaction was rolled back
        retrieved = await tenant_repo.get_by_id(tenant.id)
        assert retrieved is not None, (
            "Tenant must not be deleted when TenantService.delete_tenant() "
            "transaction rolls back mid-cascade"
        )
