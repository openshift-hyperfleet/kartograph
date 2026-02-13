"""Workspace member domain events for IAM context.

Domain events related to workspace membership management.
These events support both direct user grants and group-based grants
via the member_type field.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WorkspaceMemberSnapshot:
    """Immutable snapshot of a workspace member at deletion time.

    Used in WorkspaceDeleted to capture members that need their
    relationships cleaned up in SpiceDB.

    Attributes:
        member_id: The user ID or group ID
        member_type: "user" or "group"
        role: The role the member had
    """

    member_id: str
    member_type: str
    role: str


@dataclass(frozen=True)
class WorkspaceMemberAdded:
    """Event raised when a member (user or group) is added to a workspace.

    This event triggers creation of a role relationship in SpiceDB.

    Attributes:
        workspace_id: The ULID of the workspace
        member_id: The ID of the user or group being added
        member_type: Whether this is a USER or GROUP grant ("user" or "group")
        role: The role assigned ("admin", "editor", or "member")
        occurred_at: When the event occurred (UTC)
    """

    workspace_id: str
    member_id: str
    member_type: str
    role: str
    occurred_at: datetime


@dataclass(frozen=True)
class WorkspaceMemberRemoved:
    """Event raised when a member is removed from a workspace.

    This event triggers deletion of the role relationship in SpiceDB.

    Attributes:
        workspace_id: The ULID of the workspace
        member_id: The ID of the user or group being removed
        member_type: Whether this is a USER or GROUP grant ("user" or "group")
        role: The role the member had (needed for SpiceDB relationship deletion)
        occurred_at: When the event occurred (UTC)
    """

    workspace_id: str
    member_id: str
    member_type: str
    role: str
    occurred_at: datetime


@dataclass(frozen=True)
class WorkspaceMemberRoleChanged:
    """Event raised when a member's role is changed in a workspace.

    This event triggers deletion of the old role relationship and creation
    of the new role relationship in SpiceDB.

    Attributes:
        workspace_id: The ULID of the workspace
        member_id: The ID of the user or group
        member_type: Whether this is a USER or GROUP grant ("user" or "group")
        old_role: The previous role
        new_role: The new role
        occurred_at: When the event occurred (UTC)
    """

    workspace_id: str
    member_id: str
    member_type: str
    old_role: str
    new_role: str
    occurred_at: datetime
