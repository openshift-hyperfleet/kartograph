"""PostgreSQL + SpiceDB implementation of IGroupRepository.

This repository coordinates PostgreSQL (metadata storage) and SpiceDB
(membership and authorization) to reconstitute complete Group aggregates.

Write operations use the transactional outbox pattern - domain events are
collected from the aggregate and appended to the outbox table, rather than
writing directly to SpiceDB. This ensures atomicity and eventual consistency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, GroupMember, Role, TenantId, UserId
from iam.infrastructure.models import GroupModel
from iam.infrastructure.observability import (
    DefaultGroupRepositoryProbe,
    GroupRepositoryProbe,
)
from iam.ports.exceptions import DuplicateGroupNameError
from iam.ports.repositories import IGroupRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    ResourceType,
    format_resource,
)

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class GroupRepository(IGroupRepository):
    """Repository coordinating PostgreSQL and SpiceDB for Group aggregates.

    This implementation stores group metadata in PostgreSQL and membership
    relationships in SpiceDB. It ensures that Group aggregates are fully
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
        probe: GroupRepositoryProbe | None = None,
    ) -> None:
        """Initialize repository with database session and authorization provider.

        Args:
            session: AsyncSession from FastAPI dependency injection
            authz: Authorization provider (SpiceDB client) for reads
            outbox: Outbox repository for the transactional outbox pattern
            probe: Optional domain probe for observability
        """
        self._session = session
        self._authz = authz
        self._outbox = outbox
        self._probe = probe or DefaultGroupRepositoryProbe()

    async def save(self, group: Group) -> None:
        """Persist group metadata to PostgreSQL, events to outbox.

        Uses the transactional outbox pattern: domain events are appended
        to the outbox table within the same database transaction. The
        outbox worker will process them and write to SpiceDB.

        Args:
            group: The Group aggregate to persist

        Raises:
            DuplicateGroupNameError: If group name already exists in tenant
        """
        # Check tenant uniqueness via SpiceDB
        existing = await self.get_by_name(group.name, group.tenant_id)
        if existing and existing.id.value != group.id.value:
            self._probe.duplicate_group_name(group.name, group.tenant_id.value)
            raise DuplicateGroupNameError(
                f"Group '{group.name}' already exists in tenant {group.tenant_id.value}"
            )

        try:
            # Upsert group metadata in PostgreSQL
            stmt = select(GroupModel).where(GroupModel.id == group.id.value)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()

            if model:
                # Update existing
                model.name = group.name
                model.tenant_id = group.tenant_id.value
            else:
                # Create new
                model = GroupModel(
                    id=group.id.value,
                    tenant_id=group.tenant_id.value,
                    name=group.name,
                )
                self._session.add(model)

            # Flush to catch integrity errors before outbox writes
            await self._session.flush()

            # Collect and append events from the aggregate to outbox
            events = group.collect_events()
            for event in events:
                await self._outbox.append(
                    event,
                    aggregate_type="group",
                    aggregate_id=group.id.value,
                )

            self._probe.group_saved(group.id.value, group.tenant_id.value)

        except IntegrityError:
            # Re-raise any integrity errors (e.g., foreign key violations)
            raise

    async def get_by_id(self, group_id: GroupId) -> Group | None:
        """Fetch metadata from PostgreSQL, hydrate members from SpiceDB.

        Args:
            group_id: The unique identifier of the group

        Returns:
            The Group aggregate with members loaded, or None if not found
        """
        # Query PostgreSQL for group metadata
        stmt = select(GroupModel).where(GroupModel.id == group_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.group_not_found(group_id.value)
            return None

        # Hydrate members from SpiceDB
        try:
            members = await self._hydrate_members(group_id.value)
            self._probe.group_retrieved(group_id.value, len(members))

            return Group(
                id=GroupId(value=model.id),
                tenant_id=TenantId(value=model.tenant_id),
                name=model.name,
                members=members,
            )
        except Exception as e:
            self._probe.membership_hydration_failed(group_id.value, str(e))
            raise

    async def get_by_name(self, name: str, tenant_id: TenantId) -> Group | None:
        """Retrieve a group by name within a tenant.

        Args:
            name: The group name
            tenant_id: The tenant to search within

        Returns:
            The Group aggregate with members loaded, or None if not found
        """
        # Query PostgreSQL for group with matching name and tenant
        stmt = select(GroupModel).where(
            GroupModel.name == name,
            GroupModel.tenant_id == tenant_id.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        # Hydrate members from SpiceDB
        try:
            members = await self._hydrate_members(model.id)
            self._probe.group_retrieved(model.id, len(members))

            return Group(
                id=GroupId(value=model.id),
                tenant_id=TenantId(value=model.tenant_id),
                name=model.name,
                members=members,
            )
        except Exception as e:
            self._probe.membership_hydration_failed(model.id, str(e))
            raise

    async def list_by_tenant(self, tenant_id: TenantId) -> list[Group]:
        """List all groups in a tenant.

        Args:
            tenant_id: The tenant to list groups for

        Returns:
            List of Group aggregates (with members loaded from SpiceDB)
        """
        # Query PostgreSQL for all groups in tenant
        stmt = select(GroupModel).where(GroupModel.tenant_id == tenant_id.value)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        # Hydrate members for each group
        groups = []
        for model in models:
            try:
                members = await self._hydrate_members(model.id)
                groups.append(
                    Group(
                        id=GroupId(value=model.id),
                        tenant_id=TenantId(value=model.tenant_id),
                        name=model.name,
                        members=members,
                    )
                )
            except Exception as e:
                self._probe.membership_hydration_failed(model.id, str(e))
                # Continue with other groups
                continue

        return groups

    async def delete(self, group: Group) -> bool:
        """Delete a group and all its relationships.

        The group should have mark_for_deletion() called before this method
        to record the GroupDeleted event with member snapshot.

        Args:
            group: The group aggregate to delete (with deletion event recorded)

        Returns:
            True if deleted, False if not found
        """
        # Fetch group from PostgreSQL
        stmt = select(GroupModel).where(GroupModel.id == group.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.group_not_found(group.id.value)
            return False

        # Delete group from PostgreSQL
        await self._session.delete(model)

        # Collect and append events (should include GroupDeleted with members)
        events = group.collect_events()
        for event in events:
            await self._outbox.append(
                event,
                aggregate_type="group",
                aggregate_id=group.id.value,
            )

        self._probe.group_deleted(group.id.value)
        return True

    async def _hydrate_members(self, group_id: str) -> list[GroupMember]:
        """Fetch membership from SpiceDB and convert to domain objects.

        Args:
            group_id: The group ID to fetch members for

        Returns:
            List of GroupMember value objects
        """
        members = []
        group_resource = format_resource(ResourceType.GROUP, group_id)

        # Lookup all subjects with each role type
        for role in [Role.ADMIN, Role.MEMBER]:
            subjects = await self._authz.lookup_subjects(
                resource=group_resource,
                relation=role.value,
                subject_type=ResourceType.USER.value,
            )

            for subject_relation in subjects:
                members.append(
                    GroupMember(
                        user_id=UserId(value=subject_relation.subject_id),
                        role=Role(subject_relation.relation),
                    )
                )

        return members
