"""Domain events for IAM bounded context.

Domain events capture facts about things that have happened in the domain.
They are immutable value objects that carry all the information needed
to describe the occurrence of an event.

These events are used by the outbox pattern to ensure consistency between
PostgreSQL (application data) and SpiceDB (authorization data).
"""

from iam.domain.events.api_key import (
    APIKeyCreated,
    APIKeyDeleted,
    APIKeyRevoked,
)
from iam.domain.events.group import (
    GroupCreated,
    GroupDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
    MemberSnapshot,
)
from iam.domain.events.tenant import (
    TenantCreated,
    TenantDeleted,
    TenantMemberAdded,
    TenantMemberRemoved,
)
from iam.domain.events.workspace import (
    WorkspaceCreated,
    WorkspaceDeleted,
)
from iam.domain.events.workspace_member import (
    WorkspaceMemberAdded,
    WorkspaceMemberRemoved,
    WorkspaceMemberRoleChanged,
    WorkspaceMemberSnapshot,
)

# Type alias for all domain events in the IAM context
DomainEvent = (
    TenantCreated
    | TenantDeleted
    | TenantMemberAdded
    | TenantMemberRemoved
    | GroupCreated
    | GroupDeleted
    | MemberAdded
    | MemberRemoved
    | MemberRoleChanged
    | WorkspaceCreated
    | WorkspaceDeleted
    | WorkspaceMemberAdded
    | WorkspaceMemberRemoved
    | WorkspaceMemberRoleChanged
    | APIKeyCreated
    | APIKeyRevoked
    | APIKeyDeleted
)

__all__ = [
    # Tenant events
    "TenantCreated",
    "TenantDeleted",
    "TenantMemberAdded",
    "TenantMemberRemoved",
    # Group events
    "GroupCreated",
    "GroupDeleted",
    "MemberAdded",
    "MemberRemoved",
    "MemberRoleChanged",
    "MemberSnapshot",
    # Workspace events
    "WorkspaceCreated",
    "WorkspaceDeleted",
    # Workspace member events
    "WorkspaceMemberAdded",
    "WorkspaceMemberRemoved",
    "WorkspaceMemberRoleChanged",
    "WorkspaceMemberSnapshot",
    # API key events
    "APIKeyCreated",
    "APIKeyRevoked",
    "APIKeyDeleted",
    # Type alias
    "DomainEvent",
]
