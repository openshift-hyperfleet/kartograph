"""Repository protocols (ports) for IAM bounded context.

Repository protocols define the interface for persisting and retrieving
aggregates. Implementations coordinate PostgreSQL (metadata) and SpiceDB
(authorization/membership) to reconstitute complete aggregates.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iam.domain.aggregates import Group, User
from iam.domain.value_objects import GroupId, TenantId, UserId


@runtime_checkable
class IGroupRepository(Protocol):
    """Repository for Group aggregate persistence.

    Implementations coordinate PostgreSQL (metadata) and SpiceDB (membership).
    Returns fully hydrated Group aggregates per DDD pattern.

    Tenant context is provided via method parameters for operations that
    require tenant scoping (save, get_by_name, list_by_tenant).
    """

    async def save(self, group: Group, tenant_id: TenantId) -> None:
        """Persist a group aggregate.

        Creates a new group or updates an existing one. Persists group metadata
        to PostgreSQL and membership relationships to SpiceDB.

        Args:
            group: The Group aggregate to persist
            tenant_id: The tenant this group belongs to

        Raises:
            DuplicateGroupNameError: If group name already exists in tenant
        """
        ...

    async def get_by_id(self, group_id: GroupId) -> Group | None:
        """Retrieve a group by its ID.

        Args:
            group_id: The unique identifier of the group

        Returns:
            The Group aggregate with members loaded from SpiceDB, or None if not found
        """
        ...

    async def get_by_name(self, name: str, tenant_id: TenantId) -> Group | None:
        """Retrieve a group by name within a tenant.

        Args:
            name: The group name
            tenant_id: The tenant to search within

        Returns:
            The Group aggregate with members loaded, or None if not found
        """
        ...

    async def list_by_tenant(self, tenant_id: TenantId) -> list[Group]:
        """List all groups in a tenant.

        Args:
            tenant_id: The tenant to list groups for

        Returns:
            List of Group aggregates (with members loaded from SpiceDB)
        """
        ...

    async def delete(self, group_id: GroupId, tenant_id: TenantId) -> bool:
        """Delete a group and all its relationships.

        Removes the group from PostgreSQL and all relationships from SpiceDB
        (membership and tenant relationships).

        Args:
            group_id: The group to delete
            tenant_id: The tenant this group belongs to

        Returns:
            True if deleted, False if not found
        """
        ...


@runtime_checkable
class IUserRepository(Protocol):
    """Repository for User aggregate persistence.

    Simple repository for user metadata. Users are provisioned from SSO,
    so this repository only handles metadata storage and retrieval.
    """

    async def save(self, user: User) -> None:
        """Persist a user aggregate.

        Creates a new user or updates an existing one.

        Args:
            user: The User aggregate to persist
        """
        ...

    async def get_by_id(self, user_id: UserId) -> User | None:
        """Retrieve a user by their ID.

        Args:
            user_id: The unique identifier of the user

        Returns:
            The User aggregate, or None if not found
        """
        ...

    async def get_by_username(self, username: str) -> User | None:
        """Retrieve a user by their username.

        Args:
            username: The username to search for

        Returns:
            The User aggregate, or None if not found
        """
        ...
