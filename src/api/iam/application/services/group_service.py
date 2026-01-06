"""Group application service for IAM bounded context.

Orchestrates group creation with proper user validation and authorization setup.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import DefaultGroupServiceProbe, GroupServiceProbe
from iam.application.services.user_service import UserService
from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, Role, TenantId, UserId
from iam.ports.repositories import IGroupRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    RelationType,
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
        user_service: UserService,
        authz: AuthorizationProvider,
        probe: GroupServiceProbe | None = None,
    ):
        """Initialize GroupService with dependencies.

        Args:
            session: Database session for transaction management
            group_repository: Repository for group persistence
            user_service: Service for user management
            authz: Authorization provider for permission checks
            probe: Optional domain probe for observability
        """
        self._session = session
        self._group_repository = group_repository
        self._user_service = user_service
        self._authz = authz
        self._probe = probe or DefaultGroupServiceProbe()

    async def create_group(
        self,
        name: str,
        creator_id: UserId,
        creator_username: str,
        tenant_id: TenantId,
    ) -> Group:
        """Create a new group with creator as admin.

        Manages database transaction for the entire use case.

        Args:
            name: Group name
            creator_id: ID of user creating the group
            creator_username: Username of creator (for JIT provisioning)
            tenant_id: Tenant this group belongs to

        Returns:
            The created Group aggregate

        Raises:
            DuplicateGroupNameError: If group name already exists in tenant
            Exception: If group creation fails
        """
        try:
            async with self._session.begin():
                # Ensure creator user exists (JIT provisioning from SSO)
                await self._user_service.ensure_user(creator_id, creator_username)

                # Create group with creator as admin
                group = Group(id=GroupId.generate(), name=name)
                group.add_member(creator_id, Role.ADMIN)

                # Persist group (writes to PostgreSQL and SpiceDB)
                await self._group_repository.save(group, tenant_id)

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

        # Verify group belongs to tenant via SpiceDB
        group_resource = format_resource(ResourceType.GROUP, group_id.value)
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)

        has_access = await self._authz.check_permission(
            resource=group_resource,
            permission=RelationType.TENANT,
            subject=tenant_resource,
        )

        if not has_access:
            # Group exists but doesn't belong to this tenant
            # Return None (act as if not found) for security
            return None

        return group

    async def delete_group(self, group_id: GroupId, tenant_id: TenantId) -> bool:
        """Delete a group.

        Manages database transaction for deletion.

        Args:
            group_id: The group ID to delete
            tenant_id: The tenant this group belongs to

        Returns:
            True if deleted, False if not found
        """
        async with self._session.begin():
            return await self._group_repository.delete(group_id, tenant_id)
