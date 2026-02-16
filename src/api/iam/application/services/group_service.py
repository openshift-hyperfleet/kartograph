"""Group application service for IAM bounded context.

Orchestrates group creation with proper user validation and authorization setup.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import DefaultGroupServiceProbe, GroupServiceProbe
from iam.application.value_objects import GroupAccessGrant
from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, GroupRole, TenantId, UserId
from iam.ports.exceptions import DuplicateGroupNameError
from iam.ports.repositories import IGroupRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)


class GroupService:
    """Application service for group management.

    Orchestrates group creation with proper user validation and
    authorization setup. Manages database transactions.
    """

    def __init__(
        self,
        session: AsyncSession,
        group_repository: IGroupRepository,
        authz: AuthorizationProvider,
        scope_to_tenant: TenantId,
        probe: GroupServiceProbe | None = None,
    ):
        """Initialize GroupService with dependencies.

        Args:
            session: Database session for transaction management
            group_repository: Repository for group persistence
            authz: Authorization provider for permission checks
            scope_to_tenant: A tenant to which this service will be scoped.
            probe: Optional domain probe for observability
        """
        self._session = session
        self._group_repository = group_repository
        self._authz = authz
        self._probe = probe or DefaultGroupServiceProbe()
        self._scope_to_tenant = scope_to_tenant

    async def _check_group_permission(
        self,
        user_id: UserId,
        group_id: GroupId,
        permission: Permission,
    ) -> bool:
        """Check if user has permission on group.

        Args:
            user_id: The user to check
            group_id: The group resource
            permission: The permission to check (VIEW, MANAGE)

        Returns:
            True if user has permission, False otherwise
        """
        resource = format_resource(ResourceType.GROUP, group_id.value)
        subject = format_subject(ResourceType.USER, user_id.value)

        return await self._authz.check_permission(
            resource=resource,
            permission=permission.value,
            subject=subject,
        )

    async def create_group(
        self,
        name: str,
        creator_id: UserId,
    ) -> Group:
        """Create a new group with creator as admin.

        Manages database transaction for the entire use case.

        Args:
            name: Group name
            creator_id: ID of user creating the group

        Returns:
            The created Group aggregate

        Raises:
            DuplicateGroupNameError: If group name already exists in tenant
            Exception: If group creation fails
        """
        try:
            # Create group using factory method (records GroupCreated event)
            group = Group.create(name=name, tenant_id=self._scope_to_tenant)
            # Add creator as admin (records MemberAdded event)
            group.add_member(creator_id, GroupRole.ADMIN)

            async with self._session.begin():
                # Persist group (writes to PostgreSQL and outbox)
                await self._group_repository.save(group)

            self._probe.group_created(
                group_id=group.id.value,
                name=name,
                tenant_id=self._scope_to_tenant.value,
                creator_id=creator_id.value,
            )
            return group

        except Exception as e:
            self._probe.group_creation_failed(
                name=name,
                tenant_id=self._scope_to_tenant.value,
                error=str(e),
            )
            raise

    async def list_groups(self, user_id: UserId) -> list[Group]:
        """List groups the user has VIEW permission on.

        Filters groups in scoped tenant to only those where user has
        VIEW permission via SpiceDB lookup_resources.

        Args:
            user_id: The user requesting the list (for permission filtering)

        Returns:
            List of Group aggregates user can view
        """
        # Get all groups in tenant from database
        all_groups = await self._group_repository.list_by_tenant(
            tenant_id=self._scope_to_tenant
        )

        # Use SpiceDB lookup_resources to filter by VIEW permission
        subject = format_subject(ResourceType.USER, user_id.value)

        accessible_ids = await self._authz.lookup_resources(
            resource_type=ResourceType.GROUP,
            permission=Permission.VIEW,
            subject=subject,
        )

        # Convert to set for O(1) lookup
        accessible_set = set(accessible_ids)

        # Filter groups to only accessible ones
        accessible_groups = [g for g in all_groups if g.id.value in accessible_set]

        return accessible_groups

    async def get_group(
        self,
        group_id: GroupId,
        user_id: UserId,
    ) -> Group | None:
        """Get a group by ID with tenant scoping and VIEW permission check.

        Returns None if group doesn't exist, belongs to different tenant,
        or user lacks VIEW permission.

        Args:
            group_id: The group ID to retrieve
            user_id: The user requesting access (for permission check)

        Returns:
            The Group aggregate, or None if not found or not accessible
        """
        # Fetch group from repository
        group = await self._group_repository.get_by_id(group_id)
        if group is None:
            return None

        # Verify group belongs to scoped tenant (database check)
        if group.tenant_id != self._scope_to_tenant:
            # Don't leak existence of groups in other tenants
            return None

        # Check user has VIEW permission (SpiceDB check)
        has_view = await self._check_group_permission(
            user_id=user_id,
            group_id=group_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            # User lacks VIEW permission - act as if not found
            return None

        return group

    async def delete_group(self, group_id: GroupId, user_id: UserId) -> bool:
        """Delete a group.

        Verifies the user has manage permission on the group before deletion.
        Manages database transaction for deletion.

        Args:
            group_id: The group ID to delete
            user_id: The user attempting to delete (must have manage permission)

        Returns:
            True if deleted, False if not found

        Raises:
            PermissionError: If user lacks manage permission on the group
        """
        # Check user has manage permission on this group (SpiceDB - no session needed)
        resource = format_resource(ResourceType.GROUP, group_id.value)
        subject = format_resource(ResourceType.USER, user_id.value)
        has_permission = await self._authz.check_permission(
            resource=resource,
            permission=Permission.MANAGE,
            subject=subject,
        )
        if not has_permission:
            raise PermissionError(
                f"User {user_id.value} lacks manage permission on group {group_id.value}"
            )

        # All database operations (reads + writes) in a single transaction
        # This avoids SQLAlchemy 2.0 autobegin issues
        async with self._session.begin():
            # Load the group aggregate
            group = await self._group_repository.get_by_id(group_id)
            if group is None:
                return False

            # Verify tenant ownership
            if group.tenant_id.value != self._scope_to_tenant.value:
                return False

            # Mark for deletion (records GroupDeleted event with member snapshot)
            group.mark_for_deletion()

            return await self._group_repository.delete(group)

    async def add_member(
        self,
        group_id: GroupId,
        acting_user_id: UserId,
        user_id: UserId,
        role: GroupRole,
    ) -> Group:
        """Add a member to a group.

        Args:
            group_id: The group to add member to
            acting_user_id: User performing the action (must have MANAGE permission)
            user_id: ID of user to add
            role: The role to assign (ADMIN or MEMBER)

        Returns:
            Updated Group aggregate

        Raises:
            PermissionError: If acting user lacks MANAGE permission
            ValueError: If member already exists, group not found, or tenant mismatch
        """
        # Check acting user has MANAGE permission
        has_manage = await self._check_group_permission(
            user_id=acting_user_id,
            group_id=group_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {acting_user_id.value} lacks manage permission on group "
                f"{group_id.value}"
            )

        async with self._session.begin():
            # Load group
            group = await self._group_repository.get_by_id(group_id)
            if group is None:
                raise ValueError(f"Group {group_id.value} not found")

            # Verify tenant ownership
            if group.tenant_id.value != self._scope_to_tenant.value:
                raise ValueError("Group belongs to different tenant")

            # Add member (aggregate handles validation and events)
            group.add_member(user_id, role)

            # Save (persists events to outbox)
            await self._group_repository.save(group)

        return group

    async def remove_member(
        self,
        group_id: GroupId,
        acting_user_id: UserId,
        user_id: UserId,
    ) -> Group:
        """Remove a member from a group.

        Args:
            group_id: The group to remove member from
            acting_user_id: User performing the action (must have MANAGE permission)
            user_id: ID of user to remove

        Returns:
            Updated Group aggregate

        Raises:
            PermissionError: If acting user lacks MANAGE permission
            ValueError: If member doesn't exist, group not found, or tenant mismatch
        """
        # Check acting user has MANAGE permission
        has_manage = await self._check_group_permission(
            user_id=acting_user_id,
            group_id=group_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {acting_user_id.value} lacks manage permission on group "
                f"{group_id.value}"
            )

        async with self._session.begin():
            # Load group
            group = await self._group_repository.get_by_id(group_id)
            if group is None:
                raise ValueError(f"Group {group_id.value} not found")

            # Verify tenant ownership
            if group.tenant_id.value != self._scope_to_tenant.value:
                raise ValueError("Group belongs to different tenant")

            # Remove member (aggregate handles validation and events)
            group.remove_member(user_id)

            # Save (persists events to outbox)
            await self._group_repository.save(group)

        return group

    async def update_member_role(
        self,
        group_id: GroupId,
        acting_user_id: UserId,
        user_id: UserId,
        new_role: GroupRole,
    ) -> Group:
        """Update a member's role in a group.

        Args:
            group_id: The group
            acting_user_id: User performing the action (must have MANAGE permission)
            user_id: ID of user to update
            new_role: The new role to assign

        Returns:
            Updated Group aggregate

        Raises:
            PermissionError: If acting user lacks MANAGE permission
            ValueError: If member doesn't exist, group not found, or tenant mismatch
        """
        # Check acting user has MANAGE permission
        has_manage = await self._check_group_permission(
            user_id=acting_user_id,
            group_id=group_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {acting_user_id.value} lacks manage permission on group "
                f"{group_id.value}"
            )

        async with self._session.begin():
            # Load group
            group = await self._group_repository.get_by_id(group_id)
            if group is None:
                raise ValueError(f"Group {group_id.value} not found")

            # Verify tenant ownership
            if group.tenant_id.value != self._scope_to_tenant.value:
                raise ValueError("Group belongs to different tenant")

            # Update member role (aggregate handles validation and events)
            group.update_member_role(user_id, new_role)

            # Save (persists events to outbox)
            await self._group_repository.save(group)

        return group

    async def list_members(
        self,
        group_id: GroupId,
        user_id: UserId,
    ) -> list[GroupAccessGrant]:
        """List members of a group.

        Returns list of GroupAccessGrant objects from SpiceDB.
        User must have VIEW permission on group.

        Args:
            group_id: The group to list members for
            user_id: User requesting the list (must have VIEW permission)

        Returns:
            List of GroupAccessGrant objects

        Raises:
            PermissionError: If user lacks VIEW permission
        """
        # Check user has VIEW permission
        has_view = await self._check_group_permission(
            user_id=user_id,
            group_id=group_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            raise PermissionError(
                f"User {user_id.value} lacks view permission on group {group_id.value}"
            )

        # Read explicit tuples from SpiceDB (not computed permissions).
        # Unlike LookupSubjects which expands groups and computes permissions,
        # ReadRelationships returns only the explicitly stored tuples.
        tuples = await self._authz.read_relationships(
            resource_type=ResourceType.GROUP.value,
            resource_id=group_id.value,
        )

        members: list[GroupAccessGrant] = []

        for rel_tuple in tuples:
            # Parse subject (format: "user:ID")
            subject_parts = rel_tuple.subject.split(":")
            if len(subject_parts) < 2:
                continue

            subject_type_str = subject_parts[0]
            user_id_str = ":".join(subject_parts[1:])

            # Only process user subjects with group role relations
            if subject_type_str == "user":
                # Map SpiceDB relation to domain role
                if rel_tuple.relation == "admin":
                    role = GroupRole.ADMIN
                elif rel_tuple.relation == "member_relation":
                    role = GroupRole.MEMBER
                else:
                    continue  # Skip non-role relations (tenant, etc.)

                members.append(
                    GroupAccessGrant(
                        user_id=user_id_str,
                        role=role,
                    )
                )

        return members

    async def update_group(
        self,
        group_id: GroupId,
        user_id: UserId,
        name: str,
    ) -> Group:
        """Update group metadata (rename).

        Args:
            group_id: The group to update
            user_id: User performing the action (must have MANAGE permission)
            name: New group name

        Returns:
            Updated Group aggregate

        Raises:
            PermissionError: If user lacks MANAGE permission
            ValueError: If group not found, tenant mismatch, or name invalid
            DuplicateGroupNameError: If name already exists in tenant
        """
        # Check user has MANAGE permission
        has_manage = await self._check_group_permission(
            user_id=user_id,
            group_id=group_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {user_id.value} lacks manage permission on group "
                f"{group_id.value}"
            )

        async with self._session.begin():
            # Load group
            group = await self._group_repository.get_by_id(group_id)
            if group is None:
                raise ValueError(f"Group {group_id.value} not found")

            # Verify tenant ownership
            if group.tenant_id.value != self._scope_to_tenant.value:
                raise ValueError("Group belongs to different tenant")

            # Check name uniqueness (if name is changing)
            if name != group.name:
                existing = await self._group_repository.get_by_name(
                    name=name,
                    tenant_id=self._scope_to_tenant,
                )
                if existing:
                    raise DuplicateGroupNameError(
                        f"Group '{name}' already exists in tenant"
                    )

                # Rename via aggregate method
                group.rename(name)

            # Save
            await self._group_repository.save(group)

        return group
