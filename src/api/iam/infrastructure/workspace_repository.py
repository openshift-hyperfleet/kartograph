"""PostgreSQL + SpiceDB implementation of IWorkspaceRepository.

This repository coordinates PostgreSQL (metadata storage) and SpiceDB
(membership and authorization) to reconstitute complete Workspace aggregates.

Write operations use the transactional outbox pattern - domain events are
collected from the aggregate and appended to the outbox table, rather than
writing directly to SpiceDB. This ensures atomicity and eventual consistency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import Workspace
from iam.domain.value_objects import (
    MemberType,
    TenantId,
    WorkspaceId,
    WorkspaceMember,
    WorkspaceRole,
)
from iam.infrastructure.models import WorkspaceModel
from iam.infrastructure.observability import (
    DefaultWorkspaceRepositoryProbe,
    WorkspaceRepositoryProbe,
)
from iam.infrastructure.outbox import IAMEventSerializer
from iam.ports.repositories import IWorkspaceRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    ResourceType,
    format_resource,
)

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class WorkspaceRepository(IWorkspaceRepository):
    """Repository coordinating PostgreSQL and SpiceDB for Workspace aggregates.

    This implementation stores workspace metadata in PostgreSQL and membership
    relationships in SpiceDB. It ensures that Workspace aggregates are fully
    hydrated when retrieved, following DDD principles.

    Write operations use the transactional outbox pattern:
    - Domain events are collected from the aggregate
    - Events are appended to the outbox table (same transaction as PostgreSQL)
    - The outbox worker processes events and writes to SpiceDB
    """

    def __init__(
        self,
        session: AsyncSession,
        authz: AuthorizationProvider,
        outbox: "OutboxRepository",
        probe: WorkspaceRepositoryProbe | None = None,
        serializer: IAMEventSerializer | None = None,
    ) -> None:
        """Initialize repository with database session and authorization provider.

        Args:
            session: AsyncSession from FastAPI dependency injection
            authz: Authorization provider (SpiceDB client) for reads
            outbox: Outbox repository for the transactional outbox pattern
            probe: Optional domain probe for observability
            serializer: Optional event serializer for testability
        """
        self._session = session
        self._authz = authz
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
        """Fetch metadata from PostgreSQL, hydrate members from SpiceDB.

        Args:
            workspace_id: The unique identifier of the workspace

        Returns:
            The Workspace aggregate with members loaded, or None if not found
        """
        stmt = select(WorkspaceModel).where(WorkspaceModel.id == workspace_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.workspace_not_found(workspace_id=workspace_id.value)
            return None

        # Hydrate members from SpiceDB
        try:
            members = await self._hydrate_members(workspace_id.value)
            self._probe.workspace_retrieved(workspace_id.value, len(members))

            return self._to_domain(model, members)
        except Exception as e:
            self._probe.membership_hydration_failed(workspace_id.value, str(e))
            raise

    async def get_by_name(self, tenant_id: TenantId, name: str) -> Workspace | None:
        """Retrieve a workspace by name within a tenant.

        Args:
            tenant_id: The tenant to search within
            name: The workspace name

        Returns:
            The Workspace aggregate with members loaded, or None if not found
        """
        stmt = select(WorkspaceModel).where(
            WorkspaceModel.tenant_id == tenant_id.value,
            WorkspaceModel.name == name,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.workspace_not_found(
                tenant_id=tenant_id.value,
                name=name,
            )
            return None

        # Hydrate members from SpiceDB
        try:
            members = await self._hydrate_members(model.id)
            self._probe.workspace_retrieved(model.id, len(members))

            return self._to_domain(model, members)
        except Exception as e:
            self._probe.membership_hydration_failed(model.id, str(e))
            raise

    async def get_root_workspace(self, tenant_id: TenantId) -> Workspace | None:
        """Fetch the root workspace for a tenant.

        Args:
            tenant_id: The tenant to find the root workspace for

        Returns:
            The root Workspace aggregate with members loaded, or None if not found
        """
        stmt = select(WorkspaceModel).where(
            WorkspaceModel.tenant_id == tenant_id.value,
            WorkspaceModel.is_root == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.workspace_not_found(
                tenant_id=tenant_id.value,
                is_root=True,
            )
            return None

        # Hydrate members from SpiceDB
        try:
            members = await self._hydrate_members(model.id)
            self._probe.workspace_retrieved(model.id, len(members))

            return self._to_domain(model, members)
        except Exception as e:
            self._probe.membership_hydration_failed(model.id, str(e))
            raise

    async def list_by_tenant(self, tenant_id: TenantId) -> list[Workspace]:
        """List all workspaces in a tenant.

        Args:
            tenant_id: The tenant to list workspaces for

        Returns:
            List of Workspace aggregates (with members loaded from SpiceDB)
        """
        # Query PostgreSQL for all workspaces in tenant
        stmt = select(WorkspaceModel).where(WorkspaceModel.tenant_id == tenant_id.value)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        # Hydrate members for each workspace
        workspaces = []
        for model in models:
            try:
                members = await self._hydrate_members(model.id)
                workspaces.append(self._to_domain(model, members))
            except Exception as e:
                self._probe.membership_hydration_failed(model.id, str(e))
                # Continue with other workspaces
                continue

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

    def _to_domain(
        self,
        model: WorkspaceModel,
        members: list[WorkspaceMember] | None = None,
    ) -> Workspace:
        """Convert a WorkspaceModel to a Workspace domain aggregate.

        Reconstitutes the aggregate from database state without generating
        any domain events (this is a read operation, not a mutation).

        Args:
            model: The SQLAlchemy model to convert
            members: Optional list of hydrated workspace members from SpiceDB

        Returns:
            A Workspace domain aggregate with members populated
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
            members=members or [],
        )

    async def _hydrate_members(self, workspace_id: str) -> list[WorkspaceMember]:
        """Fetch membership from SpiceDB and convert to domain objects.

        Queries all combinations of roles (ADMIN, EDITOR, MEMBER) and member
        types (USER, GROUP) to fully hydrate workspace membership.

        Uses set-based deduplication because SpiceDB's LookupSubjects can
        return the same subject multiple times when subject relations resolve
        through multiple permission paths (e.g., group#member is a permission
        = admin + member_relation in the schema).

        Args:
            workspace_id: The workspace ID to fetch members for

        Returns:
            List of WorkspaceMember value objects (deduplicated)
        """
        seen: set[WorkspaceMember] = set()
        members: list[WorkspaceMember] = []
        workspace_resource = format_resource(ResourceType.WORKSPACE, workspace_id)

        # Lookup all subjects with each role and member type combination
        for role in [WorkspaceRole.ADMIN, WorkspaceRole.EDITOR, WorkspaceRole.MEMBER]:
            for member_type in [MemberType.USER, MemberType.GROUP]:
                subjects = await self._authz.lookup_subjects(
                    resource=workspace_resource,
                    relation=role.value,
                    subject_type=member_type.value,
                    optional_subject_relation=(
                        "member" if member_type == MemberType.GROUP else None
                    ),
                )

                for subject_relation in subjects:
                    workspace_member = WorkspaceMember(
                        member_id=subject_relation.subject_id,
                        member_type=member_type,
                        role=WorkspaceRole(subject_relation.relation),
                    )
                    if workspace_member not in seen:
                        seen.add(workspace_member)
                        members.append(workspace_member)

        return members
