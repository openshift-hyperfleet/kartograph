"""Workspace aggregate for IAM context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from iam.domain.events import (
    WorkspaceCreated,
    WorkspaceDeleted,
)
from iam.domain.value_objects import TenantId, WorkspaceId

if TYPE_CHECKING:
    from iam.domain.events import DomainEvent


@dataclass
class Workspace:
    """Workspace aggregate representing a container for knowledge graphs.

    Workspaces organize knowledge graphs within a tenant. Each tenant has
    exactly one root workspace (auto-created on tenant creation), and can
    have multiple child workspaces.

    Business rules:
    - Workspace names must be 1-512 characters
    - Cannot have both is_root=True and parent_workspace_id set
    - Root workspace must have is_root=True and parent_workspace_id=None
    - Cannot delete root workspace (enforced at service layer)

    Event collection:
    - All mutating operations record domain events
    - Events can be collected via collect_events() for the outbox pattern
    """

    id: WorkspaceId
    tenant_id: TenantId
    name: str
    parent_workspace_id: Optional[WorkspaceId]
    is_root: bool
    created_at: datetime
    updated_at: datetime
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate business rules after initialization."""
        self._validate_name(self.name)
        self._validate_root_and_parent()

    def _validate_name(self, name: str) -> None:
        """Validate workspace name length."""
        if not name or len(name) < 1 or len(name) > 512:
            raise ValueError("Workspace name must be between 1 and 512 characters")

    def _validate_root_and_parent(self) -> None:
        """Validate that root workspaces don't have parents."""
        if self.is_root and self.parent_workspace_id is not None:
            raise ValueError(
                "A root workspace cannot have a parent workspace. "
                "Either set is_root=False or parent_workspace_id=None"
            )

    @classmethod
    def create(
        cls,
        name: str,
        tenant_id: TenantId,
        parent_workspace_id: WorkspaceId,
    ) -> "Workspace":
        """Factory method for creating a new child workspace.

        This is the proper DDD way to create aggregates. It generates the ID,
        initializes the aggregate, and records the WorkspaceCreated event.

        Use create_root() instead for creating root workspaces. This method
        is exclusively for child workspaces that must have a parent.

        Args:
            name: The name of the workspace (1-512 characters)
            tenant_id: The tenant this workspace belongs to
            parent_workspace_id: The parent workspace in the hierarchy (required)

        Returns:
            A new Workspace aggregate with WorkspaceCreated event recorded

        Raises:
            ValueError: If name is empty or exceeds 512 characters
        """
        now = datetime.now(UTC)
        workspace = cls(
            id=WorkspaceId.generate(),
            tenant_id=tenant_id,
            name=name,
            parent_workspace_id=parent_workspace_id,
            is_root=False,
            created_at=now,
            updated_at=now,
        )
        workspace._pending_events.append(
            WorkspaceCreated(
                workspace_id=workspace.id.value,
                tenant_id=tenant_id.value,
                name=name,
                parent_workspace_id=parent_workspace_id.value,
                is_root=False,
                occurred_at=now,
            )
        )
        return workspace

    @classmethod
    def create_root(
        cls,
        name: str,
        tenant_id: TenantId,
    ) -> "Workspace":
        """Factory method for creating a root workspace.

        Each tenant should have exactly one root workspace. This method
        creates a workspace with is_root=True and no parent.

        Args:
            name: The name of the workspace (1-512 characters)
            tenant_id: The tenant this workspace belongs to

        Returns:
            A new root Workspace aggregate with WorkspaceCreated event recorded

        Raises:
            ValueError: If name is empty or exceeds 512 characters
        """
        now = datetime.now(UTC)
        workspace = cls(
            id=WorkspaceId.generate(),
            tenant_id=tenant_id,
            name=name,
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )
        workspace._pending_events.append(
            WorkspaceCreated(
                workspace_id=workspace.id.value,
                tenant_id=tenant_id.value,
                name=name,
                parent_workspace_id=None,
                is_root=True,
                occurred_at=datetime.now(UTC),
            )
        )
        return workspace

    def mark_for_deletion(self) -> None:
        """Mark the workspace for deletion and record the WorkspaceDeleted event.

        Note: Business rule enforcement (cannot delete root workspace,
        cannot delete workspace with children) is handled at the service layer.
        """
        self._pending_events.append(
            WorkspaceDeleted(
                workspace_id=self.id.value,
                tenant_id=self.tenant_id.value,
                occurred_at=datetime.now(UTC),
            )
        )

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear pending domain events.

        This method returns all domain events that have been recorded since
        the last call to collect_events(). It clears the internal list, so
        subsequent calls will return an empty list until new events are recorded.

        Returns:
            List of pending domain events
        """
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events
