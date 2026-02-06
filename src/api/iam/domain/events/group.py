"""Group domain events for IAM context.

Domain events related to group lifecycle and membership management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
