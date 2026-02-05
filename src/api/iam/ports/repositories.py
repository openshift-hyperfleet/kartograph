"""Repository protocols (ports) for IAM bounded context.

Repository protocols define the interface for persisting and retrieving
aggregates. Implementations coordinate PostgreSQL (metadata) and SpiceDB
(authorization/membership) to reconstitute complete aggregates.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from iam.domain.aggregates import APIKey, Group, Tenant, User
from iam.domain.value_objects import APIKeyId, GroupId, TenantId, UserId

from shared_kernel.authorization.protocols import AuthorizationProvider


@runtime_checkable
class IGroupRepository(Protocol):
    """Repository for Group aggregate persistence.

    Implementations coordinate PostgreSQL (metadata) and SpiceDB (membership).
    Returns fully hydrated Group aggregates per DDD pattern.

    The Group aggregate contains tenant_id, so tenant context is self-contained.
    Only get_by_name and list_by_tenant require tenant_id as a query parameter.
    """

    async def save(self, group: Group) -> None:
        """Persist a group aggregate.

        Creates a new group or updates an existing one. Persists group metadata
        to PostgreSQL and domain events to the outbox.

        Args:
            group: The Group aggregate to persist (includes tenant_id)

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

    async def delete(self, group: Group) -> bool:
        """Delete a group and all its relationships.

        The group should have mark_for_deletion() called before this method
        to record the GroupDeleted event with member snapshot. The outbox
        worker will handle removing relationships from SpiceDB.

        Args:
            group: The Group aggregate to delete (with deletion event recorded)

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


@runtime_checkable
class ITenantRepository(Protocol):
    """Repository for Tenant aggregate persistence.

    Simple repository for tenant metadata. Tenants represent organizations
    and are the top-level isolation boundary in the system.
    """

    async def save(self, tenant: Tenant) -> None:
        """Persist a tenant aggregate.

        Creates a new tenant or updates an existing one. Persists tenant
        metadata to PostgreSQL and domain events to the outbox.

        Args:
            tenant: The Tenant aggregate to persist

        Raises:
            DuplicateTenantNameError: If tenant name already exists
        """
        ...

    async def get_by_id(self, tenant_id: TenantId) -> Tenant | None:
        """Retrieve a tenant by its ID.

        Args:
            tenant_id: The unique identifier of the tenant

        Returns:
            The Tenant aggregate, or None if not found
        """
        ...

    async def get_by_name(self, name: str) -> Tenant | None:
        """Retrieve a tenant by name.

        Args:
            name: The tenant name

        Returns:
            The Tenant aggregate, or None if not found
        """
        ...

    async def list_all(self) -> list[Tenant]:
        """List all tenants in the system.

        Returns:
            List of all Tenant aggregates
        """
        ...

    async def delete(self, tenant: Tenant) -> bool:
        """Delete a tenant.

        The tenant should have mark_for_deletion() called before this method
        to record the TenantDeleted event. The outbox worker will handle any
        necessary cleanup in SpiceDB.

        Args:
            tenant: The Tenant aggregate to delete (with deletion event recorded)

        Returns:
            True if deleted, False if not found
        """
        ...

    async def is_last_admin(
        self, tenant_id: TenantId, user_id: UserId, authz: "AuthorizationProvider"
    ) -> bool:
        """Check if user is the last admin in the tenant.

        Queries to determine if this user is the only one with
        admin permissions on the tenant.

        Args:
            tenant_id: The tenant to check
            user_id: The user to check
            authz: Authorization provider for admin check

        Returns:
            True if user is the last admin, False otherwise
        """
        ...


@runtime_checkable
class IAPIKeyRepository(Protocol):
    """Repository for APIKey aggregate persistence.

    Simple repository for API key metadata and authentication lookup.
    API keys provide programmatic access as an alternative to OIDC tokens.
    """

    async def save(self, api_key: APIKey) -> None:
        """Persist an API key aggregate.

        Creates a new API key or updates an existing one. Persists API key
        metadata to PostgreSQL and domain events to the outbox.

        Args:
            api_key: The APIKey aggregate to persist

        Raises:
            DuplicateAPIKeyNameError: If key name already exists for user in tenant
        """
        ...

    async def get_by_id(
        self, api_key_id: APIKeyId, user_id: UserId, tenant_id: TenantId
    ) -> APIKey | None:
        """Retrieve an API key by its ID with user/tenant scoping.

        Security note: Requires user_id and tenant_id to prevent cross-user access.

        Args:
            api_key_id: The unique identifier of the API key
            user_id: The user who owns the key (for access control)
            tenant_id: The tenant the key belongs to (for access control)

        Returns:
            The APIKey aggregate, or None if not found or access denied
        """
        ...

    async def get_verified_key(
        self,
        secret: str,
        extract_prefix_fn: Callable[[str], str],
        verify_hash_fn: Callable[[str, str], bool],
    ) -> APIKey | None:
        """Retrieve an API key by verifying its secret.

        Extracts the prefix from the secret, queries for all keys with that
        prefix, and verifies the hash for each. Handles prefix collisions
        gracefully by iterating through candidates.

        If a collision is detected, an ERROR-level probe event is logged.

        Args:
            secret: The plaintext API key secret to verify
            extract_prefix_fn: Function to extract prefix from secret
            verify_hash_fn: Function to verify secret against hash

        Returns:
            The APIKey aggregate if secret verifies, None otherwise
        """
        ...

    async def list(
        self,
        tenant_id: TenantId,
        api_key_ids: list[APIKeyId] | None = None,
        created_by_user_id: UserId | None = None,
    ) -> list[APIKey]:
        """List API keys with optional filters.

        General-purpose list method that supports filtering by IDs, tenant,
        and creator. Filters are combined with AND logic. The repository
        doesn't know or care about authorization - it just filters by criteria.

        Args:
            api_key_ids: Optional list of specific API key IDs to include
            tenant_id: required tenant to scope the list to
            created_by_user_id: Optional filter for keys created by this user

        Returns:
            List of APIKey aggregates matching all provided filters
        """
        ...

    async def delete(self, api_key: APIKey) -> bool:
        """Delete an API key.

        The API key should have revoke() called before deletion to record
        the APIKeyRevoked event for the outbox.

        Args:
            api_key: The APIKey aggregate to delete (with revoke event recorded)

        Returns:
            True if deleted, False if not found
        """
        ...
