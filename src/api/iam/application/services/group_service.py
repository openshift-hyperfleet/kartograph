"""Group application service for IAM bounded context.

Orchestrates group creation with proper user validation and authorization setup.
"""

from __future__ import annotations

from iam.application.observability import DefaultGroupServiceProbe, GroupServiceProbe
from iam.application.services.user_service import UserService
from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, Role, TenantId, UserId
from iam.ports.repositories import IGroupRepository


class GroupService:
    """Application service for group management.

    Orchestrates group creation with proper user validation and
    authorization setup.
    """

    def __init__(
        self,
        group_repository: IGroupRepository,
        user_service: UserService,
        probe: GroupServiceProbe | None = None,
    ):
        """Initialize GroupService with dependencies.

        Args:
            group_repository: Repository for group persistence
            user_service: Service for user management
            probe: Optional domain probe for observability
        """
        self._group_repository = group_repository
        self._user_service = user_service
        self._probe = probe or DefaultGroupServiceProbe()

    async def create_group(
        self,
        name: str,
        creator_id: UserId,
        creator_username: str,
        tenant_id: TenantId,
    ) -> Group:
        """Create a new group with creator as admin.

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
