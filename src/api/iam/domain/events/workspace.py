"""Workspace domain events for IAM context.

Domain events related to workspace lifecycle management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from iam.domain.events.workspace_member import WorkspaceMemberSnapshot


@dataclass(frozen=True)
class WorkspaceCreated:
    """Event raised when a new workspace is created.

    This event triggers the creation of a tenant relationship in SpiceDB.

    Attributes:
        workspace_id: The ULID of the created workspace
        tenant_id: The ULID of the tenant the workspace belongs to
        name: The name of the workspace
        parent_workspace_id: The ULID of the parent workspace (None for root)
        is_root: Whether this is the root workspace for the tenant
        occurred_at: When the event occurred (UTC)
    """

    workspace_id: str
    tenant_id: str
    name: str
    parent_workspace_id: Optional[str]
    is_root: bool
    occurred_at: datetime


@dataclass(frozen=True)
class WorkspaceDeleted:
    """Event raised when a workspace is deleted.

    This event triggers the deletion of all relationships for this workspace
    in SpiceDB. Carries a snapshot of the workspace's parent relationship,
    root status, and members to ensure proper cleanup without external lookups.

    Attributes:
        workspace_id: The ULID of the deleted workspace
        tenant_id: The ULID of the tenant the workspace belonged to
        parent_workspace_id: The parent workspace ID (if this is a child workspace)
        is_root: Whether this was a root workspace
        members: Snapshot of members at deletion time
        occurred_at: When the event occurred (UTC)
    """

    workspace_id: str
    tenant_id: str
    parent_workspace_id: Optional[str]
    is_root: bool
    members: tuple[WorkspaceMemberSnapshot, ...]
    occurred_at: datetime


@dataclass(frozen=True)
class WorkspaceCreatorTenantSet:
    """Event raised when a root workspace's creator_tenant relation is established.

    This event triggers the creation of a creator_tenant relationship in SpiceDB,
    which allows all tenant members to create child workspaces under this root
    workspace via the create_child permission.

    Only emitted for root workspaces during creation.

    Attributes:
        workspace_id: The ULID of the root workspace
        tenant_id: The ULID of the tenant whose members gain create_child permission
        occurred_at: When the event occurred (UTC)
    """

    workspace_id: str
    tenant_id: str
    occurred_at: datetime
