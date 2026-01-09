"""Group application service for IAM bounded context.

Orchestrates group creation with proper user validation and authorization setup.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import DefaultGroupServiceProbe, GroupServiceProbe
from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, Role, TenantId, UserId
from iam.ports.repositories import IGroupRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
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
        probe: GroupServiceProbe | None = None,
    ):
        """Initialize GroupService with dependencies.

        Args:
            session: Database session for transaction management
            group_repository: Repository for group persistence
            authz: Authorization provider for permission checks
            probe: Optional domain probe for observability
        """
        self._session = session
        self._group_repository = group_repository
        self._authz = authz
        self._probe = probe or DefaultGroupServiceProbe()

    async def create_group(
        self,
        name: str,
        creator_id: UserId,
        tenant_id: TenantId,
    ) -> Group:
        """Create a new group with creator as admin.

        Manages database transaction for the entire use case.

        Args:
            name: Group name
            creator_id: ID of user creating the group
            tenant_id: Tenant this group belongs to

        Returns:
            The created Group aggregate

        Raises:
            DuplicateGroupNameError: If group name already exists in tenant
            Exception: If group creation fails
        """
        try:
            # Create group using factory method (records GroupCreated event)
            group = Group.create(name=name, tenant_id=tenant_id)
            # Add creator as admin (records MemberAdded event)
            group.add_member(creator_id, Role.ADMIN)

            async with self._session.begin():
                # Persist group (writes to PostgreSQL and outbox)
                await self._group_repository.save(group)

            self._probe.group_created(
                group_id=group.id.value,
                name=name,
                tenant_id=tenant_id.value,
                creator_id=creator_id.value,
            )
            return group

        except Exception as e:
            self._probe.group_creation_failed(
                name=name,
                tenant_id=tenant_id.value,
                error=str(e),
            )
            raise

    async def get_group(self, group_id: GroupId, tenant_id: TenantId) -> Group | None:
        """Get a group by ID with tenant isolation.

        Verifies the group belongs to the specified tenant via SpiceDB.

        Args:
            group_id: The group ID to retrieve
            tenant_id: The tenant context (from auth)

        Returns:
            The Group aggregate, or None if not found or not accessible
        """
        # Fetch group from repository
        group = await self._group_repository.get_by_id(group_id)
        if group is None:
            return None

        # Verify group belongs to the expected tenant
        if group.tenant_id.value != tenant_id.value:
            # Group exists but doesn't belong to this tenant
            # Return None (act as if not found) for security
            return None

        return group

    async def delete_group(
        self, group_id: GroupId, tenant_id: TenantId, user_id: UserId
    ) -> bool:
        """Delete a group.

        Verifies the user has manage permission on the group before deletion.
        Manages database transaction for deletion.

        Args:
            group_id: The group ID to delete
            tenant_id: The tenant this group belongs to
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
            if group.tenant_id.value != tenant_id.value:
                return False

            # Mark for deletion (records GroupDeleted event with member snapshot)
            group.mark_for_deletion()

            return await self._group_repository.delete(group)
