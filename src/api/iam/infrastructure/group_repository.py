"""PostgreSQL + SpiceDB implementation of IGroupRepository.

This repository coordinates PostgreSQL (metadata storage) and SpiceDB
(membership and authorization) to reconstitute complete Group aggregates.
"""

from __future__ import annotations

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
    format_subject,
)


class GroupRepository(IGroupRepository):
    """Repository coordinating PostgreSQL and SpiceDB for Group aggregates.

    This implementation stores group metadata in PostgreSQL and membership
    relationships in SpiceDB. It ensures that Group aggregates are fully
    hydrated when retrieved, following DDD principles.
    """

    def __init__(
        self,
        session: AsyncSession,
        authz: AuthorizationProvider,
        probe: GroupRepositoryProbe | None = None,
    ) -> None:
        """Initialize repository with database session and authorization provider.

        Args:
            session: AsyncSession from FastAPI dependency injection
            authz: Authorization provider (SpiceDB client)
            probe: Optional domain probe for observability
        """
        self._session = session
        self._authz = authz
        self._probe = probe or DefaultGroupRepositoryProbe()

    async def save(self, group: Group, tenant_id: TenantId) -> None:
        """Persist group metadata to PostgreSQL, membership to SpiceDB.

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

            # Flush to catch integrity errors before SpiceDB writes
            await self._session.flush()

            # Write tenant relationship to SpiceDB
            group_resource = format_resource(ResourceType.GROUP, group.id.value)
            tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)
            await self._authz.write_relationship(
                resource=group_resource,
                relation="tenant",
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
        # Query PostgreSQL for all groups with this name
        stmt = select(GroupModel).where(GroupModel.name == name)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        # Check each group to find one that belongs to the specified tenant
        for model in models:
            # Verify group belongs to tenant via SpiceDB
            try:
                group_resource = format_resource(ResourceType.GROUP, model.id)
                tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)

                # Check if group has tenant relationship in SpiceDB
                has_relationship = await self._authz.check_permission(
                    resource=group_resource,
                    permission="tenant",
                    subject=tenant_resource,
                )

                if has_relationship:
                    # This group belongs to the tenant - hydrate and return
                    members = await self._hydrate_members(model.id)
                    self._probe.group_retrieved(model.id, len(members))

                    return Group(
                        id=GroupId(value=model.id),
                        name=model.name,
                        members=members,
                    )
            except Exception as e:
                self._probe.membership_hydration_failed(model.id, str(e))
                # Continue checking other groups with same name
                continue

        # No group with this name belongs to the tenant
        return None

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
            permission="tenant",
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

    async def delete(self, group_id: GroupId) -> bool:
        """Delete a group and all its membership relationships.

        Args:
            group_id: The group to delete

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

        # Delete membership relationships from SpiceDB
        # Get current members first
        members = await self._hydrate_members(group_id.value)
        group_resource = format_resource(ResourceType.GROUP, group_id.value)

        for member in members:
            await self._authz.delete_relationship(
                resource=group_resource,
                relation=member.role.value,
                subject=format_subject(ResourceType.USER, member.user_id.value),
            )

        # Note: We don't delete the tenant relationship here because
        # we don't know which tenant the group belongs to without querying SpiceDB.
        # In production, consider adding a method to delete all relationships for a resource.

        # Delete group from PostgreSQL
        await self._session.delete(model)

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

        # Delete removed members
        for member_key in current_member_keys - new_member_keys:
            user_id, role = member_key
            await self._authz.delete_relationship(
                resource=group_resource,
                relation=role,
                subject=format_subject(ResourceType.USER, user_id),
            )

        # Add new members
        for member_key in new_member_keys - current_member_keys:
            user_id, role = member_key
            await self._authz.write_relationship(
                resource=group_resource,
                relation=role,
                subject=format_subject(ResourceType.USER, user_id),
            )
