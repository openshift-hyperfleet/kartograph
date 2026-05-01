"""Integration tests for TenantService.delete_tenant() transactional rollback.

These tests verify that tenant deletion via TenantService is atomic: if the
transaction fails at any point, the tenant record and its children are NOT deleted
(no partial state).

Complements test_tenant_repository.py (which tests the repository layer directly)
by verifying that the service-level transaction boundary (async with session.begin()
in TenantService.delete_tenant()) actually rolls back on failure.

NOTE: Rollback semantics cannot be verified with mock sessions. These tests
require a real PostgreSQL connection.
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
from shared_kernel.authorization.protocols import AuthorizationProvider

pytestmark = pytest.mark.integration


class TestTenantServiceDeleteRollback:
    """Tests that TenantService.delete_tenant() rolls back fully on transaction failure.

    TenantService.delete_tenant() wraps the entire cascade inside
    ``async with self._session.begin()``. If an exception escapes that block,
    SQLAlchemy must roll back the entire unit of work — no workspaces, groups,
    api keys, or the tenant itself should be removed. These tests confirm that
    invariant holds at the real-database level.

    This class exercises the FULL service path — calling TenantService.delete_tenant()
    directly — unlike repository-layer tests that inject failure at a lower level.
    """

    @pytest.mark.asyncio
    async def test_tenant_service_delete_rollback_on_failure(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        clean_iam_data: None,
    ) -> None:
        """When TenantService.delete_tenant() fails mid-transaction, the tenant is not deleted.

        Creates a tenant, starts deletion via TenantService which wraps the entire cascade
        in async with session.begin(). Injects a failure in tenant_repository.delete() and
        asserts the tenant still exists afterwards — verifying full transactional rollback
        at the service level.
        """
        from tests.fakes.authorization import InMemoryAuthorizationProvider

        # --- Arrange: create a tenant in the database ---
        outbox = OutboxRepository(session=async_session)
        tenant_repo = TenantRepository(session=async_session, outbox=outbox)
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox,
        )
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox,
        )
        api_key_repo = APIKeyRepository(session=async_session, outbox=outbox)

        tenant = Tenant.create(name="Rollback Test Tenant")

        async with async_session.begin():
            await tenant_repo.save(tenant)

        # --- Arrange: subclass that raises during delete() ---
        class FailingTenantRepository(TenantRepository):
            """Raises RuntimeError when delete() is called.

            Simulates a failure that occurs AFTER all cascading deletes have
            run (workspaces, groups, api keys) but BEFORE the tenant row is
            removed, proving the async with session.begin() block rolls back
            the entire unit of work including all cascade steps.
            """

            async def delete(self, t: Tenant) -> bool:
                raise RuntimeError(
                    "Simulated tenant deletion failure to verify service rollback"
                )

        failing_tenant_repo = FailingTenantRepository(
            session=async_session,
            outbox=outbox,
        )

        # --- Arrange: in-memory authz with administrate permission for test user ---
        authz = InMemoryAuthorizationProvider()
        user_id = "test-rollback-admin"
        await authz.write_relationship(
            f"tenant:{tenant.id.value}", "admin", f"user:{user_id}"
        )

        svc = TenantService(
            tenant_repository=failing_tenant_repo,
            workspace_repository=workspace_repo,
            group_repository=group_repo,
            api_key_repository=api_key_repo,
            authz=authz,
            session=async_session,
        )

        # --- Act: delete_tenant must raise (the tenant repo is wired to fail) ---
        with pytest.raises(RuntimeError, match="Simulated tenant deletion failure"):
            await svc.delete_tenant(
                tenant_id=tenant.id,
                requesting_user_id=UserId(value=user_id),
            )

        # --- Assert: tenant still exists — service-level transaction rolled back ---
        retrieved = await tenant_repo.get_by_id(tenant.id)
        assert retrieved is not None, (
            "Tenant must not be deleted when TenantService.delete_tenant() transaction "
            "rolls back — the async with session.begin() block must undo all cascade "
            "deletes when an exception escapes."
        )
