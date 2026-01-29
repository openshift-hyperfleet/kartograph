"""Domain events for IAM context.

Domain events capture facts about things that have happened in the domain.
They are immutable value objects that carry all the information needed
to describe the occurrence of an event.

These events are used by the outbox pattern to ensure consistency between
PostgreSQL (application data) and SpiceDB (authorization data).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class MemberSnapshot:
    """Immutable snapshot of a member's state at a point in time.

    Used in GroupDeleted and TenantDeleted
    to capture the members that need to have their
    relationships cleaned up in SpiceDB.

    Attributes:
        user_id: The ULID of the user
        role: The role the user had in the group/tenant
    """

    user_id: str
    role: str


@dataclass(frozen=True)
class GroupCreated:
    """Event raised when a new group is created.

    This event triggers the creation of a tenant relationship in SpiceDB.

    Attributes:
        group_id: The ULID of the created group
        tenant_id: The ULID of the tenant the group belongs to
        occurred_at: When the event occurred (UTC)
    """

    group_id: str
    tenant_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class GroupDeleted:
    """Event raised when a group is deleted.

    This event triggers the deletion of all relationships for this group
    in SpiceDB. The event carries a snapshot of the members at deletion time
    to ensure all relationships can be cleaned up without external lookups.

    Attributes:
        group_id: The ULID of the deleted group
        tenant_id: The ULID of the tenant the group belonged to
        members: Snapshot of members at deletion time
        occurred_at: When the event occurred (UTC)
    """

    group_id: str
    tenant_id: str
    members: tuple[MemberSnapshot, ...]
    occurred_at: datetime


@dataclass(frozen=True)
class MemberAdded:
    """Event raised when a member is added to a group.

    This event triggers the creation of a role relationship in SpiceDB.

    Attributes:
        group_id: The ULID of the group
        user_id: The ULID of the user being added
        role: The role assigned to the member (ADMIN or MEMBER)
        occurred_at: When the event occurred (UTC)
    """

    group_id: str
    user_id: str
    role: str
    occurred_at: datetime


@dataclass(frozen=True)
class MemberRemoved:
    """Event raised when a member is removed from a group.

    This event triggers the deletion of the role relationship in SpiceDB.

    Attributes:
        group_id: The ULID of the group
        user_id: The ULID of the user being removed
        role: The role the member had (needed to identify the relationship to delete)
        occurred_at: When the event occurred (UTC)
    """

    group_id: str
    user_id: str
    role: str
    occurred_at: datetime


@dataclass(frozen=True)
class MemberRoleChanged:
    """Event raised when a member's role is changed.

    This event triggers both a deletion of the old role relationship
    and creation of a new role relationship in SpiceDB.

    Attributes:
        group_id: The ULID of the group
        user_id: The ULID of the user whose role changed
        old_role: The previous role
        new_role: The new role
        occurred_at: When the event occurred (UTC)
    """

    group_id: str
    user_id: str
    old_role: str
    new_role: str
    occurred_at: datetime


@dataclass(frozen=True)
class TenantCreated:
    """Event raised when a new tenant is created.

    This event captures the fact that a tenant has been created.
    For the walking skeleton, no SpiceDB relationships are automatically
    created (those will be set when assigning tenant admins).

    Attributes:
        tenant_id: The ULID of the created tenant
        name: The name of the tenant
        occurred_at: When the event occurred (UTC)
    """

    tenant_id: str
    name: str
    occurred_at: datetime


@dataclass(frozen=True)
class TenantDeleted:
    """Event raised when a tenant is deleted.

    This event captures the fact that a tenant has been deleted.
    Any cleanup of related resources (groups, etc.) should be handled
    by cascade rules or separate processes.

    Attributes:
        tenant_id: The ULID of the deleted tenant
        occurred_at: When the event occurred (UTC)
        members: The members of the tenant that must be cleaned-up
    """

    tenant_id: str
    occurred_at: datetime
    members: tuple[MemberSnapshot, ...]


@dataclass(frozen=True)
class TenantMemberAdded:
    """Event raised when a user is added as a member to a tenant.

    Attributes:
        tenant_id: The ID of the tenant to which the member was added
        user_id: The user added as a member to the tenant
        role: The role the user is given within the tenant
        added_by: The [optional] ID of the user that initiated this action
        occurred_at: When this even occurred (UTC)
    """

    tenant_id: str
    user_id: str
    role: str
    occurred_at: datetime
    added_by: Optional[str] = None


@dataclass(frozen=True)
class TenantMemberRemoved:
    """Event raised when a user is removed as a member from a tenant.

    Attributes:
        tenant_id: The ID of the tenant from which the member was removed
        user_id: The user removed as a member from the tenant
        removed_by: The ID of the user that initiated this action
        occurred_at: When this even occurred (UTC)
    """

    tenant_id: str
    user_id: str
    occurred_at: datetime
    removed_by: str


@dataclass(frozen=True)
class TenantMemberAdded:
    """Event raised when a user is added as a member to a tenant.

    Attributes:
        tenant_id: The ID of the tenant to which the member was added
        user_id: The user added as a member to the tenant
        role: The role the user is given within the tenant
        added_by: The [optional] ID of the user that initiated this action
        occurred_at: When this even occurred (UTC)
    """

    tenant_id: TenantId
    user_id: UserId
    role: TenantRole
    occurred_at: datetime
    added_by: Optional[UserId] = None


@dataclass(frozen=True)
class TenantMemberRemoved:
    """Event raised when a user is removed as a member from a tenant.

    Attributes:
        tenant_id: The ID of the tenant from which the member was removed
        user_id: The user removed as a member from the tenant
        removed_by: The ID of the user that initiated this action
        occurred_at: When this even occurred (UTC)
    """

    tenant_id: TenantId
    user_id: UserId
    occurred_at: datetime
    removed_by: UserId


@dataclass(frozen=True)
class APIKeyCreated:
    """Event raised when a new API key is created.

    This event captures the creation of an API key for programmatic access.

    Attributes:
        api_key_id: The ULID of the created API key
        user_id: The ULID of the user who owns the key
        tenant_id: The ULID of the tenant the key belongs to
        name: The name/description of the key
        prefix: The key prefix for identification (e.g., karto_ab)
        occurred_at: When the event occurred (UTC)
    """

    api_key_id: str
    user_id: str
    tenant_id: str
    name: str
    prefix: str
    occurred_at: datetime


@dataclass(frozen=True)
class APIKeyRevoked:
    """Event raised when an API key is revoked.

    This event captures the revocation of an API key, making it unusable.
    SpiceDB relationships are preserved for audit trail.

    Attributes:
        api_key_id: The ULID of the revoked API key
        user_id: The ULID of the user who owned the key
        occurred_at: When the event occurred (UTC)
    """

    api_key_id: str
    user_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class APIKeyDeleted:
    """Event raised when an API key is permanently deleted.

    This event is used for cascade deletion (e.g., tenant deletion)
    and triggers cleanup of all SpiceDB relationships. Unlike revocation,
    this removes the key entirely from the system.

    Attributes:
        api_key_id: The ULID of the deleted API key
        user_id: The ULID of the user who owned the key
        tenant_id: The ULID of the tenant the key belonged to
        occurred_at: When the event occurred (UTC)
    """

    api_key_id: str
    user_id: str
    tenant_id: str
    occurred_at: datetime


# Type alias for all domain events in the IAM context
DomainEvent = (
    GroupCreated
    | GroupDeleted
    | MemberAdded
    | MemberRemoved
    | MemberRoleChanged
    | TenantCreated
    | TenantDeleted
    | TenantMemberAdded
    | TenantMemberRemoved
    | APIKeyCreated
    | APIKeyRevoked
    | APIKeyDeleted
)
