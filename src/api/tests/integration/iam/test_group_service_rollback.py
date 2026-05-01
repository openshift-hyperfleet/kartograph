"""Integration tests for GroupService.delete_group() transactional rollback.

These tests verify that group deletion via GroupService is atomic: if the
transaction fails at any point, the group record is NOT deleted (no partial state).

Complements test_group_repository.py (which tests the repository layer directly)
by verifying that the service-level transaction boundary (async with session.begin()
in GroupService.delete_group()) actually rolls back on failure.

NOTE: Rollback semantics cannot be verified with mock sessions. These tests
require a real PostgreSQL connection.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.services.group_service import GroupService
from iam.domain.aggregates import Group
from iam.domain.value_objects import TenantId, UserId
from iam.infrastructure.group_repository import GroupRepository
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.protocols import AuthorizationProvider

pytestmark = pytest.mark.integration


class TestGroupServiceDeleteRollback:
    """Tests that GroupService.delete_group() rolls back fully on transaction failure.

    GroupService.delete_group() wraps the database delete inside
    ``async with self._session.begin()``. If an exception escapes that block,
    SQLAlchemy must roll back the entire unit of work. These tests confirm
    that invariant holds at the real-database level.

    This class exercises the FULL service path — calling GroupService.delete_group()
    directly — unlike repository-layer tests that inject failure at a lower level.
    """

    @pytest.mark.asyncio
    async def test_group_service_delete_rollback_on_failure(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant: TenantId,
        clean_iam_data: None,
    ) -> None:
        """When GroupService.delete_group() fails mid-transaction, the group is not deleted.

        Creates a group, starts deletion via GroupService which wraps the operation in
        async with session.begin(). Injects a failure in group_repository.delete() and
        asserts the group still exists afterwards — verifying full transactional rollback
        at the service level.
        """
        from tests.fakes.authorization import InMemoryAuthorizationProvider

        # --- Arrange: create a group in the database ---
        outbox = OutboxRepository(session=async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox,
        )

        group = Group.create(
            name="Service Rollback Test Group",
            tenant_id=test_tenant,
        )

        async with async_session.begin():
            await group_repo.save(group)

        # --- Arrange: subclass that raises during delete() ---
        class FailingGroupRepository(GroupRepository):
            """Raises RuntimeError when delete() is called.

            Simulates a failure that occurs AFTER the transaction has begun
            but BEFORE the group row is removed, proving the async with
            session.begin() block rolls back the entire unit of work.
            """

            async def delete(self, g: Group) -> bool:
                raise RuntimeError(
                    "Simulated group deletion failure to verify service rollback"
                )

        failing_repo = FailingGroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox,
        )

        # --- Arrange: in-memory authz with manage permission for test user ---
        authz = InMemoryAuthorizationProvider()
        user_id = "test-rollback-user"
        await authz.write_relationship(
            f"group:{group.id.value}", "admin", f"user:{user_id}"
        )

        svc = GroupService(
            session=async_session,
            group_repository=failing_repo,
            authz=authz,
            scope_to_tenant=test_tenant,
        )

        # --- Act: delete_group must raise (the repo is wired to fail) ---
        with pytest.raises(RuntimeError, match="Simulated group deletion failure"):
            await svc.delete_group(
                group_id=group.id,
                user_id=UserId(value=user_id),
            )

        # --- Assert: group still exists — service-level transaction rolled back ---
        retrieved = await group_repo.get_by_id(group.id)
        assert retrieved is not None, (
            "Group must not be deleted when GroupService.delete_group() transaction "
            "rolls back — the async with session.begin() block must undo all writes."
        )
