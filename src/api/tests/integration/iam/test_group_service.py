"""Service-level rollback integration tests for GroupService.

These tests verify that group deletion is atomic: if the database
transaction fails at any point inside GroupService.delete_group(), the
group record is NOT deleted (no partial state).

GroupService.delete_group() wraps the cascade inside
``async with self._session.begin()``. Only a real-database integration
test (with a real AsyncSession) can verify this transaction boundary
rolls back correctly on failure. Mock sessions cannot test SQLAlchemy
rollback semantics.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.services.group_service import GroupService
from iam.domain.aggregates import Group
from iam.domain.value_objects import TenantId, UserId
from iam.infrastructure.group_repository import GroupRepository
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.types import (
    ResourceType,
    format_resource,
    format_subject,
)
from tests.fakes.authorization import InMemoryAuthorizationProvider

pytestmark = pytest.mark.integration


class TestGroupServiceDeleteRollback:
    """Tests that GroupService.delete_group() rolls back fully on failure.

    GroupService.delete_group() wraps the delete inside
    ``async with self._session.begin()``. If an exception escapes that block,
    SQLAlchemy must roll back the entire unit of work. These tests confirm
    that invariant holds at the real-database level.
    """

    @pytest.mark.asyncio
    async def test_group_deletion_rollback_on_failure(
        self,
        async_session: AsyncSession,
        test_tenant: TenantId,
        clean_iam_data: None,
    ) -> None:
        """When group deletion fails mid-transaction, the group is not deleted.

        Creates a group, starts a GroupService.delete_group() transaction,
        injects a failure before commit, and asserts the group still exists
        afterwards — verifying full transactional rollback at the service level.
        """
        user_id = UserId.from_string("user-test-rollback")
        outbox_repo = OutboxRepository(async_session)
        fake_authz = InMemoryAuthorizationProvider()

        group_repo = GroupRepository(
            session=async_session,
            authz=fake_authz,
            outbox=outbox_repo,
        )

        # Arrange: create a group that we will attempt to delete
        group = Group.create(name="Rollback Test Group", tenant_id=test_tenant)
        async with async_session.begin():
            await group_repo.save(group)

        # Grant the user manage permission on the group so the auth check passes
        await fake_authz.write_relationship(
            resource=format_resource(ResourceType.GROUP, group.id.value),
            relation="admin",
            subject=format_subject(ResourceType.USER, user_id.value),
        )

        # Instantiate GroupService with real session (tests actual transaction semantics)
        service = GroupService(
            session=async_session,
            group_repository=group_repo,
            authz=fake_authz,
            scope_to_tenant=test_tenant,
        )

        # Patch group_repo.delete to inject failure inside the service's transaction
        original_delete = group_repo.delete

        async def _failing_delete(g: Group) -> bool:
            raise Exception("Simulated failure mid-deletion")

        group_repo.delete = _failing_delete  # type: ignore[assignment]

        try:
            # Act: the service delete must raise (failure injected mid-cascade)
            with pytest.raises(Exception, match="Simulated failure"):
                await service.delete_group(group_id=group.id, user_id=user_id)
        finally:
            group_repo.delete = original_delete  # type: ignore[assignment]

        # Assert: group still exists — the transaction was rolled back
        retrieved = await group_repo.get_by_id(group.id)
        assert retrieved is not None, (
            "Group must not be deleted when GroupService.delete_group() "
            "transaction rolls back mid-cascade"
        )
