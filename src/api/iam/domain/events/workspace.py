"""Workspace domain events for IAM context.

Domain events related to workspace lifecycle management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
    in SpiceDB.

    Attributes:
        workspace_id: The ULID of the deleted workspace
        tenant_id: The ULID of the tenant the workspace belonged to
        occurred_at: When the event occurred (UTC)
    """

    workspace_id: str
    tenant_id: str
    occurred_at: datetime
