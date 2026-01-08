"""PostgreSQL + SpiceDB implementation of IGroupRepository.

This repository coordinates PostgreSQL (metadata storage) and SpiceDB
(membership and authorization) to reconstitute complete Group aggregates.

For write operations, the repository uses the outbox pattern - domain events
are collected from the aggregate and appended to the outbox table, rather than
writing directly to SpiceDB. This ensures atomicity and eventual consistency.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import Group
from iam.domain.events import GroupCreated, GroupDeleted
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
    RelationshipSpec,
    RelationType,
    ResourceType,
    format_resource,
    format_subject,
)

if TYPE_CHECKING:
    from shared_kernel.outbox.repository import OutboxRepository


class GroupRepository(IGroupRepository):
    """Repository coordinating PostgreSQL and SpiceDB for Group aggregates.

    This implementation stores group metadata in PostgreSQL and membership
    relationships in SpiceDB. It ensures that Group aggregates are fully
    hydrated when retrieved, following DDD principles.

    Write operations use the outbox pattern:
    - Domain events are collected from the aggregate
    - Events are appended to the outbox table (same transaction as PostgreSQL)
    - The outbox worker processes events and writes to SpiceDB
    """

    def __init__(
        self,
        session: AsyncSession,
        authz: AuthorizationProvider,
        probe: GroupRepositoryProbe | None = None,
        outbox: "OutboxRepository | None" = None,
    ) -> None:
        """Initialize repository with database session and authorization provider.

        Args:
            session: AsyncSession from FastAPI dependency injection
            authz: Authorization provider (SpiceDB client) for reads
            probe: Optional domain probe for observability
            outbox: Optional outbox repository for the transactional outbox pattern
        """
        self._session = session
        self._authz = authz
        self._probe = probe or DefaultGroupRepositoryProbe()
        self._outbox = outbox

    async def save(self, group: Group, tenant_id: TenantId) -> None:
        """Persist group metadata to PostgreSQL, events to outbox.

        Uses the transactional outbox pattern: instead of writing directly
        to SpiceDB, domain events are appended to the outbox table within
        the same database transaction. The outbox worker will process them.

        Args:
            group: The Group aggregate to persist
            tenant_id: The tenant this group belongs to

        Raises:
            DuplicateGroupNameError: If group name already exists in tenant
        """
        # Check tenant uniqueness via SpiceDB
        existing = await self.get_by_name(group.name, tenant_id)
        if existing and existing.id.value != group.id.value:
            self._probe.duplicate_group_name(group.name, tenant_id.value)
            raise DuplicateGroupNameError(
                f"Group '{group.name}' already exists in tenant {tenant_id.value}"
            )

        try:
            # Upsert group metadata in PostgreSQL
            stmt = select(GroupModel).where(GroupModel.id == group.id.value)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()

            is_new = model is None

            if model:
                # Update existing
                model.name = group.name
            else:
                # Create new
                model = GroupModel(
                    id=group.id.value,
                    name=group.name,
                )
                self._session.add(model)

            # Flush to catch integrity errors before outbox writes
            await self._session.flush()

            # Use outbox pattern if available
            if self._outbox:
                # For new groups, append GroupCreated event
                if is_new:
                    group_created = GroupCreated(
                        group_id=group.id.value,
                        tenant_id=tenant_id.value,
                        occurred_at=datetime.now(UTC),
                    )
                    await self._outbox.append(
                        group_created,
                        aggregate_type="group",
                        aggregate_id=group.id.value,
                    )

                # Collect and append events from the aggregate
                events = group.collect_events()
                for event in events:
                    await self._outbox.append(
                        event,
                        aggregate_type="group",
                        aggregate_id=group.id.value,
                    )
            else:
                # Fallback: direct SpiceDB writes (for backward compatibility)
                group_resource = format_resource(ResourceType.GROUP, group.id.value)
                tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)
                await self._authz.write_relationship(
                    resource=group_resource,
                    relation=RelationType.TENANT,
                    subject=tenant_resource,
                )
                # Sync membership relationships to SpiceDB
                await self._sync_members_to_spicedb(group, tenant_id)

            self._probe.group_saved(group.id.value, tenant_id.value)

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
        # Query SpiceDB for all group IDs in this tenant
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)
        group_ids = await self._authz.lookup_resources(
            resource_type=ResourceType.GROUP.value,
            permission=RelationType.TENANT,
            subject=tenant_resource,
        )

        if not group_ids:
            # No groups in this tenant
            return None

        # Query PostgreSQL for group with matching name AND id in tenant
        stmt = select(GroupModel).where(
            GroupModel.name == name, GroupModel.id.in_(group_ids)
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
        # Query SpiceDB to get all group IDs for this tenant (O(1) operation)
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)
        group_ids = await self._authz.lookup_resources(
            resource_type=ResourceType.GROUP.value,
            permission=RelationType.TENANT,
            subject=tenant_resource,
        )

        if not group_ids:
            # No groups in this tenant
            return []

        # Fetch only those groups from PostgreSQL (single query with IN clause)
        stmt = select(GroupModel).where(GroupModel.id.in_(group_ids))
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
                        name=model.name,
                        members=members,
                    )
                )
            except Exception as e:
                self._probe.membership_hydration_failed(model.id, str(e))
                # Continue with other groups
                continue

        return groups

    async def delete(self, group_id: GroupId, tenant_id: TenantId) -> bool:
        """Delete a group and all its relationships.

        Removes the group from PostgreSQL and appends GroupDeleted event
        to the outbox (or directly deletes from SpiceDB if outbox not available).

        Args:
            group_id: The group to delete
            tenant_id: The tenant this group belongs to

        Returns:
            True if deleted, False if not found
        """
        # Fetch group from PostgreSQL
        stmt = select(GroupModel).where(GroupModel.id == group_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.group_not_found(group_id.value)
            return False

        # Delete group from PostgreSQL first
        await self._session.delete(model)

        # Use outbox pattern if available
        if self._outbox:
            # Append GroupDeleted event - the worker will delete from SpiceDB
            group_deleted = GroupDeleted(
                group_id=group_id.value,
                tenant_id=tenant_id.value,
                occurred_at=datetime.now(UTC),
            )
            await self._outbox.append(
                group_deleted,
                aggregate_type="group",
                aggregate_id=group_id.value,
            )
        else:
            # Fallback: direct SpiceDB deletes
            group_resource = format_resource(ResourceType.GROUP, group_id.value)
            tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)

            # Delete all relationships from SpiceDB in a single bulk operation
            # Build list of relationships to delete (members + tenant)
            members = await self._hydrate_members(group_id.value)
            relationships_to_delete = []

            # Add member relationships
            for member in members:
                relationships_to_delete.append(
                    RelationshipSpec(
                        resource=group_resource,
                        relation=member.role.value,
                        subject=format_subject(ResourceType.USER, member.user_id.value),
                    )
                )

            # Add tenant relationship
            relationships_to_delete.append(
                RelationshipSpec(
                    resource=group_resource,
                    relation=RelationType.TENANT,
                    subject=tenant_resource,
                )
            )

            # Bulk delete in single SpiceDB request
            await self._authz.delete_relationships(relationships_to_delete)

        self._probe.group_deleted(group_id.value)
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

    async def _sync_members_to_spicedb(self, group: Group, tenant_id: TenantId) -> None:
        """Sync group membership to SpiceDB.

        Args:
            group: The group with members to sync
            tenant_id: The tenant this group belongs to
        """
        group_resource = format_resource(ResourceType.GROUP, group.id.value)

        # Fetch current members from SpiceDB
        current_members = await self._hydrate_members(group.id.value)

        # Build sets for comparison
        current_member_keys = {(m.user_id.value, m.role.value) for m in current_members}
        new_member_keys = {(m.user_id.value, m.role.value) for m in group.members}

        # Build bulk delete list for removed members
        deletes = []
        for member_key in current_member_keys - new_member_keys:
            user_id, role = member_key
            deletes.append(
                RelationshipSpec(
                    resource=group_resource,
                    relation=role,
                    subject=format_subject(ResourceType.USER, user_id),
                )
            )

        # Build bulk write list for new members
        writes = []
        for member_key in new_member_keys - current_member_keys:
            user_id, role = member_key
            writes.append(
                RelationshipSpec(
                    resource=group_resource,
                    relation=role,
                    subject=format_subject(ResourceType.USER, user_id),
                )
            )

        # Execute bulk operations
        if deletes:
            await self._authz.delete_relationships(deletes)

        if writes:
            await self._authz.write_relationships(writes)
