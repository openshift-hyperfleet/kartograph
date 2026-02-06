"""PostgreSQL implementation of IWorkspaceRepository.

This repository manages workspace metadata storage in PostgreSQL.
Unlike GroupRepository, it doesn't need SpiceDB for membership hydration
since workspaces don't have members yet (Phase 3).

Write operations use the transactional outbox pattern - domain events are
collected from the aggregate and appended to the outbox table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId, WorkspaceId
from iam.infrastructure.models import WorkspaceModel
from iam.infrastructure.observability import (
    DefaultWorkspaceRepositoryProbe,
    WorkspaceRepositoryProbe,
)
from iam.infrastructure.outbox import IAMEventSerializer
from iam.ports.repositories import IWorkspaceRepository

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class WorkspaceRepository(IWorkspaceRepository):
    """Repository managing PostgreSQL storage for Workspace aggregates.

    This implementation stores workspace metadata in PostgreSQL only.
    Workspaces are simple aggregates with no complex relationships
    requiring SpiceDB hydration (that comes in Phase 3).

    Write operations use the transactional outbox pattern:
    - Domain events are collected from the aggregate
    - Events are appended to the outbox table (same transaction as PostgreSQL)
    - The outbox worker processes events if needed
    """

    def __init__(
        self,
        session: AsyncSession,
        outbox: "OutboxRepository",
        probe: WorkspaceRepositoryProbe | None = None,
        serializer: IAMEventSerializer | None = None,
    ) -> None:
        """Initialize repository with database session and outbox.

        Args:
            session: AsyncSession from FastAPI dependency injection
            outbox: Outbox repository for the transactional outbox pattern
            probe: Optional domain probe for observability
            serializer: Optional event serializer for testability
        """
        self._session = session
        self._outbox = outbox
        self._probe = probe or DefaultWorkspaceRepositoryProbe()
        self._serializer = serializer or IAMEventSerializer()

    async def save(self, workspace: Workspace) -> None:
        """Persist workspace metadata to PostgreSQL, events to outbox.

        Uses the transactional outbox pattern: domain events are appended
        to the outbox table within the same database transaction.

        Args:
            workspace: The Workspace aggregate to persist
        """
        # Upsert workspace metadata in PostgreSQL
        stmt = select(WorkspaceModel).where(WorkspaceModel.id == workspace.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            # Update existing
            model.name = workspace.name
            model.parent_workspace_id = (
                workspace.parent_workspace_id.value
                if workspace.parent_workspace_id
                else None
            )
            model.is_root = workspace.is_root
            model.updated_at = workspace.updated_at
        else:
            # Create new
            model = WorkspaceModel(
                id=workspace.id.value,
                tenant_id=workspace.tenant_id.value,
                name=workspace.name,
                parent_workspace_id=(
                    workspace.parent_workspace_id.value
                    if workspace.parent_workspace_id
                    else None
                ),
                is_root=workspace.is_root,
                created_at=workspace.created_at,
                updated_at=workspace.updated_at,
            )
            self._session.add(model)

        # Flush to catch integrity errors before outbox writes
        await self._session.flush()

        # Collect, serialize, and append events from the aggregate to outbox
        events = workspace.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="workspace",
                aggregate_id=workspace.id.value,
            )

        self._probe.workspace_saved(workspace.id.value, workspace.tenant_id.value)

    async def get_by_id(self, workspace_id: WorkspaceId) -> Workspace | None:
        """Fetch workspace metadata from PostgreSQL.

        Args:
            workspace_id: The unique identifier of the workspace

        Returns:
            The Workspace aggregate, or None if not found
        """
        stmt = select(WorkspaceModel).where(WorkspaceModel.id == workspace_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.workspace_not_found(workspace_id.value)
            return None

        workspace = self._to_domain(model)
        self._probe.workspace_retrieved(workspace.id.value)
        return workspace

    async def get_by_name(self, tenant_id: TenantId, name: str) -> Workspace | None:
        """Fetch workspace by name within a tenant.

        Args:
            tenant_id: The tenant to search within
            name: The workspace name

        Returns:
            The Workspace aggregate, or None if not found
        """
        stmt = select(WorkspaceModel).where(
            WorkspaceModel.tenant_id == tenant_id.value,
            WorkspaceModel.name == name,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        workspace = self._to_domain(model)
        self._probe.workspace_retrieved(workspace.id.value)
        return workspace

    async def get_root_workspace(self, tenant_id: TenantId) -> Workspace | None:
        """Fetch the root workspace for a tenant.

        Args:
            tenant_id: The tenant to find the root workspace for

        Returns:
            The root Workspace aggregate, or None if not found
        """
        stmt = select(WorkspaceModel).where(
            WorkspaceModel.tenant_id == tenant_id.value,
            WorkspaceModel.is_root == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        workspace = self._to_domain(model)
        self._probe.workspace_retrieved(workspace.id.value)
        return workspace

    async def list_by_tenant(self, tenant_id: TenantId) -> list[Workspace]:
        """Fetch all workspaces in a tenant.

        Args:
            tenant_id: The tenant to list workspaces for

        Returns:
            List of Workspace aggregates in the tenant
        """
        stmt = select(WorkspaceModel).where(WorkspaceModel.tenant_id == tenant_id.value)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        workspaces = [self._to_domain(model) for model in models]
        self._probe.workspaces_listed(tenant_id.value, len(workspaces))
        return workspaces

    async def delete(self, workspace: Workspace) -> bool:
        """Delete workspace from PostgreSQL and emit domain events.

        The workspace should have mark_for_deletion() called before this
        method to record the WorkspaceDeleted event.

        Args:
            workspace: The Workspace aggregate to delete (with deletion event recorded)

        Returns:
            True if deleted, False if not found
        """
        stmt = select(WorkspaceModel).where(WorkspaceModel.id == workspace.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        # Collect and append deletion event to outbox before deletion
        events = workspace.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="workspace",
                aggregate_id=workspace.id.value,
            )

        # Delete from PostgreSQL
        await self._session.delete(model)
        await self._session.flush()

        self._probe.workspace_deleted(workspace.id.value)
        return True

    def _to_domain(self, model: WorkspaceModel) -> Workspace:
        """Convert a WorkspaceModel to a Workspace domain aggregate.

        Reconstitutes the aggregate from database state without generating
        any domain events (this is a read operation, not a mutation).

        Args:
            model: The SQLAlchemy model to convert

        Returns:
            A Workspace domain aggregate
        """
        return Workspace(
            id=WorkspaceId(value=model.id),
            tenant_id=TenantId(value=model.tenant_id),
            name=model.name,
            parent_workspace_id=(
                WorkspaceId(value=model.parent_workspace_id)
                if model.parent_workspace_id
                else None
            ),
            is_root=model.is_root,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
