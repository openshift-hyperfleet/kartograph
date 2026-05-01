"""Integration tests for workspace deletion transactional rollback.

These tests verify that workspace deletion is atomic: if the transaction fails
at any point, the workspace record is NOT deleted (no partial state).

NOTE: Rollback semantics cannot be verified with mock sessions. These tests
require a real PostgreSQL connection.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId
from iam.infrastructure.workspace_repository import WorkspaceRepository
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.protocols import AuthorizationProvider

pytestmark = pytest.mark.integration


class TestWorkspaceDeleteRollback:
    """Tests that workspace deletion rolls back fully on transaction failure.

    workspace_service.delete_workspace() wraps the delete inside
    ``async with self._session.begin()``. If an exception escapes that block,
    SQLAlchemy must roll back the entire unit of work. These tests confirm
    that invariant holds at the real-database level.
    """

    @pytest.mark.asyncio
    async def test_workspace_deletion_rollback_on_failure(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant: TenantId,
        clean_iam_data: None,
    ) -> None:
        """When workspace deletion fails mid-transaction, the workspace is not deleted.

        Creates a child workspace, starts a deletion transaction, injects a
        failure before commit, and asserts the workspace still exists
        afterwards — verifying full transactional rollback.
        """
        outbox_repo = OutboxRepository(async_session)
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Arrange: create a root workspace so we can attach a child
        root_ws = Workspace.create_root(
            name="Rollback Root WS",
            tenant_id=test_tenant,
        )
        async with async_session.begin():
            await workspace_repo.save(root_ws)

        # Create the child workspace that we will attempt to delete
        child_ws = Workspace.create(
            name="Rollback Child WS",
            tenant_id=test_tenant,
            parent_workspace_id=root_ws.id,
        )
        async with async_session.begin():
            await workspace_repo.save(child_ws)

        # Act: mark for deletion inside a transaction that we abort mid-way
        try:
            async with async_session.begin():
                child_ws.mark_for_deletion()
                await workspace_repo.delete(child_ws)
                # Inject failure before the transaction commits
                raise Exception("Simulated failure mid-deletion")
        except Exception:
            pass  # Expected: the transaction must roll back

        # Assert: workspace still exists — deletion was rolled back
        retrieved = await workspace_repo.get_by_id(child_ws.id)
        assert retrieved is not None, (
            "Workspace must not be deleted when the transaction rolls back"
        )
