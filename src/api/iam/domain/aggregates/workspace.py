"""Workspace aggregate for IAM context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from iam.domain.events import (
    WorkspaceCreated,
    WorkspaceDeleted,
    WorkspaceMemberAdded,
    WorkspaceMemberRemoved,
    WorkspaceMemberRoleChanged,
)
from iam.domain.events.workspace_member import WorkspaceMemberSnapshot
from iam.domain.observability.workspace_probe import (
    DefaultWorkspaceProbe,
    WorkspaceProbe,
)
from iam.domain.value_objects import (
    MemberType,
    TenantId,
    WorkspaceId,
    WorkspaceMember,
    WorkspaceRole,
)

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
    - A member (same member_id + member_type) cannot be added twice

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
    members: list[WorkspaceMember] = field(default_factory=list)
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)
    _probe: WorkspaceProbe = field(
        default_factory=DefaultWorkspaceProbe,
        repr=False,
    )

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
        probe: WorkspaceProbe | None = None,
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
            probe: Optional observability probe for domain events

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
            _probe=probe or DefaultWorkspaceProbe(),
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
        probe: WorkspaceProbe | None = None,
    ) -> "Workspace":
        """Factory method for creating a root workspace.

        Each tenant should have exactly one root workspace. This method
        creates a workspace with is_root=True and no parent.

        Args:
            name: The name of the workspace (1-512 characters)
            tenant_id: The tenant this workspace belongs to
            probe: Optional observability probe for domain events

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
            _probe=probe or DefaultWorkspaceProbe(),
        )
        workspace._pending_events.append(
            WorkspaceCreated(
                workspace_id=workspace.id.value,
                tenant_id=tenant_id.value,
                name=name,
                parent_workspace_id=None,
                is_root=True,
                occurred_at=now,
            )
        )
        return workspace

    def add_member(
        self,
        member_id: str,
        member_type: MemberType,
        role: WorkspaceRole,
    ) -> None:
        """Add a member (user or group) to the workspace.

        Args:
            member_id: The user ID or group ID
            member_type: Whether this is a USER or GROUP
            role: The role to assign (ADMIN, EDITOR, or MEMBER)

        Raises:
            TypeError: If member_id is not a string, or if member_type/role
                are not the correct enum types
            ValueError: If member_id is empty or member is already added
        """
        # Validate member_id type
        if not isinstance(member_id, str):
            raise TypeError(f"member_id must be str, got {type(member_id).__name__}")

        # Normalize member_id by stripping whitespace
        member_id = member_id.strip()

        # Validate non-empty
        if not member_id:
            raise ValueError("member_id cannot be empty")

        # Validate enum types
        if not isinstance(member_type, MemberType):
            raise TypeError(
                f"member_type must be MemberType, got {type(member_type).__name__}"
            )
        if not isinstance(role, WorkspaceRole):
            raise TypeError(f"role must be WorkspaceRole, got {type(role).__name__}")

        if self.has_member(member_id, member_type):
            raise ValueError(
                f"{member_type.value} {member_id} is already a member of this workspace"
            )

        member = WorkspaceMember(
            member_id=member_id,
            member_type=member_type,
            role=role,
        )
        self.members.append(member)

        self._pending_events.append(
            WorkspaceMemberAdded(
                workspace_id=self.id.value,
                member_id=member_id,
                member_type=member_type.value,
                role=role.value,
                occurred_at=datetime.now(UTC),
            )
        )
        self._probe.member_added(
            workspace_id=self.id.value,
            member_id=member_id,
            member_type=member_type.value,
            role=role.value,
        )

    def remove_member(
        self,
        member_id: str,
        member_type: MemberType,
    ) -> None:
        """Remove a member from the workspace.

        Args:
            member_id: The user ID or group ID
            member_type: Whether this is a USER or GROUP

        Raises:
            TypeError: If member_id is not a string, or if member_type is not
                the correct enum type
            ValueError: If member_id is empty or member is not in workspace
            RuntimeError: If invariant is violated
        """
        # Validate member_id type
        if not isinstance(member_id, str):
            raise TypeError(f"member_id must be str, got {type(member_id).__name__}")

        # Normalize member_id by stripping whitespace
        member_id = member_id.strip()

        # Validate non-empty
        if not member_id:
            raise ValueError("member_id cannot be empty")

        # Validate enum type
        if not isinstance(member_type, MemberType):
            raise TypeError(
                f"member_type must be MemberType, got {type(member_type).__name__}"
            )

        if not self.has_member(member_id, member_type):
            raise ValueError(
                f"{member_type.value} {member_id} is not a member of this workspace"
            )

        # Get role for event (need to know which relation to delete in SpiceDB)
        member_role = self.get_member_role(member_id, member_type)
        if member_role is None:
            raise RuntimeError(
                f"Invariant violated: member exists but role is None "
                f"(member_id={member_id}, member_type={member_type})"
            )

        # Remove from list
        self.members = [
            m
            for m in self.members
            if not (m.member_id == member_id and m.member_type == member_type)
        ]

        self._pending_events.append(
            WorkspaceMemberRemoved(
                workspace_id=self.id.value,
                member_id=member_id,
                member_type=member_type.value,
                role=member_role.value,
                occurred_at=datetime.now(UTC),
            )
        )
        self._probe.member_removed(
            workspace_id=self.id.value,
            member_id=member_id,
            member_type=member_type.value,
            role=member_role.value,
        )

    def update_member_role(
        self,
        member_id: str,
        member_type: MemberType,
        new_role: WorkspaceRole,
    ) -> None:
        """Update a member's role.

        Args:
            member_id: The user ID or group ID
            member_type: Whether this is a USER or GROUP
            new_role: The new role to assign

        Raises:
            TypeError: If member_id is not a string, or if member_type/new_role
                are not the correct enum types
            ValueError: If member_id is empty, member is not in workspace,
                or role unchanged
            RuntimeError: If invariant is violated
        """
        # Validate member_id type
        if not isinstance(member_id, str):
            raise TypeError(f"member_id must be str, got {type(member_id).__name__}")

        # Normalize member_id by stripping whitespace
        member_id = member_id.strip()

        # Validate non-empty
        if not member_id:
            raise ValueError("member_id cannot be empty")

        # Validate enum types
        if not isinstance(member_type, MemberType):
            raise TypeError(
                f"member_type must be MemberType, got {type(member_type).__name__}"
            )
        if not isinstance(new_role, WorkspaceRole):
            raise TypeError(
                f"new_role must be WorkspaceRole, got {type(new_role).__name__}"
            )

        if not self.has_member(member_id, member_type):
            raise ValueError(
                f"{member_type.value} {member_id} is not a member of this workspace"
            )

        old_role = self.get_member_role(member_id, member_type)
        if old_role is None:
            raise RuntimeError(
                f"Invariant violated: member exists but role is None "
                f"(member_id={member_id}, member_type={member_type})"
            )

        if old_role == new_role:
            raise ValueError(f"Member already has role {new_role.value}")

        # Update in-memory member list
        for i, member in enumerate(self.members):
            if member.member_id == member_id and member.member_type == member_type:
                self.members[i] = WorkspaceMember(
                    member_id=member_id,
                    member_type=member_type,
                    role=new_role,
                )
                break

        self._pending_events.append(
            WorkspaceMemberRoleChanged(
                workspace_id=self.id.value,
                member_id=member_id,
                member_type=member_type.value,
                old_role=old_role.value,
                new_role=new_role.value,
                occurred_at=datetime.now(UTC),
            )
        )
        self._probe.member_role_changed(
            workspace_id=self.id.value,
            member_id=member_id,
            member_type=member_type.value,
            old_role=old_role.value,
            new_role=new_role.value,
        )

    def rename(self, new_name: str) -> None:
        """Rename the workspace.

        Args:
            new_name: New workspace name (1-512 characters)

        Raises:
            ValueError: If name is invalid or unchanged
        """
        # Validate name
        self._validate_name(new_name)

        # Check if actually changing
        if new_name == self.name:
            raise ValueError("New name is the same as current name")

        # Update name
        self.name = new_name
        self.updated_at = datetime.now(UTC)

    def has_member(self, member_id: str, member_type: MemberType) -> bool:
        """Check if a member exists in this workspace.

        Args:
            member_id: The user ID or group ID
            member_type: Whether this is a USER or GROUP

        Returns:
            True if member exists, False otherwise
        """
        return any(
            m.member_id == member_id and m.member_type == member_type
            for m in self.members
        )

    def get_member_role(
        self, member_id: str, member_type: MemberType
    ) -> WorkspaceRole | None:
        """Get a member's role.

        Args:
            member_id: The user ID or group ID
            member_type: Whether this is a USER or GROUP

        Returns:
            The member's role, or None if not a member
        """
        for member in self.members:
            if member.member_id == member_id and member.member_type == member_type:
                return member.role
        return None

    def mark_for_deletion(self) -> None:
        """Mark the workspace for deletion and record the WorkspaceDeleted event.

        Captures a snapshot of the workspace's parent relationship, root status,
        and members to ensure proper cleanup of SpiceDB relationships.

        Note: Business rule enforcement (cannot delete root workspace,
        cannot delete workspace with children) is handled at the service layer.
        """
        # Create member snapshot for SpiceDB cleanup
        members_snapshot = tuple(
            WorkspaceMemberSnapshot(
                member_id=m.member_id,
                member_type=m.member_type.value,
                role=m.role.value,
            )
            for m in self.members
        )

        self._pending_events.append(
            WorkspaceDeleted(
                workspace_id=self.id.value,
                tenant_id=self.tenant_id.value,
                parent_workspace_id=self.parent_workspace_id.value
                if self.parent_workspace_id
                else None,
                is_root=self.is_root,
                members=members_snapshot,
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
