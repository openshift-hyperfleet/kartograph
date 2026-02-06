"""Tenant domain events for IAM context.

Domain events related to tenant lifecycle and membership management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from iam.domain.events.group import MemberSnapshot


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
        occurred_at: When this event occurred (UTC)
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
        occurred_at: When this event occurred (UTC)
    """

    tenant_id: str
    user_id: str
    occurred_at: datetime
    removed_by: str
