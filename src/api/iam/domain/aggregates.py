"""Domain aggregates for IAM context.

Aggregates are the core business objects containing state and business logic.
They enforce invariants and business rules without depending on infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from iam.domain.events import (
    GroupCreated,
    GroupDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
    MemberSnapshot,
    TenantCreated,
    TenantDeleted,
)
from iam.domain.value_objects import GroupId, GroupMember, Role, TenantId, UserId

if TYPE_CHECKING:
    from iam.domain.events import DomainEvent


@dataclass
class Group:
    """Group aggregate representing a collection of users working together.

    Groups are the primary unit for resource sharing and collaboration.
    Each group belongs to a tenant and membership relationships are managed
    through the authorization system (SpiceDB).

    Business rules:
    - A group must have at least one admin at all times
    - Users can only be added once
    - Members have roles (ADMIN, MEMBER)

    Event collection:
    - All mutating operations record domain events
    - Events can be collected via collect_events() for the outbox pattern
    """

    id: GroupId
    tenant_id: TenantId
    name: str
    members: list[GroupMember] = field(default_factory=list)
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(cls, name: str, tenant_id: TenantId) -> "Group":
        """Factory method for creating a new group.

        This is the proper DDD way to create aggregates. It generates the ID,
        initializes the aggregate, and records the GroupCreated event.

        Args:
            name: The name of the group
            tenant_id: The tenant this group belongs to

        Returns:
            A new Group aggregate with GroupCreated event recorded
        """
        group = cls(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name=name,
        )
        group._pending_events.append(
            GroupCreated(
                group_id=group.id.value,
                tenant_id=tenant_id.value,
                occurred_at=datetime.now(UTC),
            )
        )
        return group

    def add_member(self, user_id: UserId, role: Role) -> None:
        """Add a member to the group with a specific role.

        Args:
            user_id: The user to add
            role: The role to assign (ADMIN or MEMBER)

        Raises:
            ValueError: If user is already a member
        """
        if self.has_member(user_id):
            raise ValueError(f"User {user_id} is already a member of this group")

        member = GroupMember(user_id=user_id, role=role)
        self.members.append(member)

        self._pending_events.append(
            MemberAdded(
                group_id=self.id.value,
                user_id=user_id.value,
                role=role,
                occurred_at=datetime.now(UTC),
            )
        )

    def remove_member(self, user_id: UserId) -> None:
        """Remove a member from the group.

        Args:
            user_id: The user to remove

        Raises:
            ValueError: If user is not a member or is the last admin
        """
        if not self.has_member(user_id):
            raise ValueError(f"User {user_id} is not a member of this group")

        member_role = self.get_member_role(user_id)

        # Check if removing last admin
        if member_role == Role.ADMIN:
            admin_count = sum(1 for m in self.members if m.role == Role.ADMIN)
            if admin_count == 1:
                raise ValueError(
                    "Cannot remove the last admin. Promote another member first."
                )

        self.members = [m for m in self.members if m.user_id != user_id]

        # member_role is guaranteed non-None since we checked has_member above
        self._pending_events.append(
            MemberRemoved(
                group_id=self.id.value,
                user_id=user_id.value,
                role=member_role,  # type: ignore[arg-type]
                occurred_at=datetime.now(UTC),
            )
        )

    def update_member_role(self, user_id: UserId, new_role: Role) -> None:
        """Update a member's role.

        Args:
            user_id: The user whose role to update
            new_role: The new role to assign

        Raises:
            ValueError: If user is not a member or is the last admin being demoted
        """
        if not self.has_member(user_id):
            raise ValueError(f"User {user_id} is not a member of this group")

        current_role = self.get_member_role(user_id)

        # Check if demoting last admin
        if current_role == Role.ADMIN and new_role != Role.ADMIN:
            admin_count = sum(1 for m in self.members if m.role == Role.ADMIN)
            if admin_count == 1:
                raise ValueError(
                    "Cannot demote the last admin. Promote another member first."
                )

        self.members = [
            GroupMember(user_id=m.user_id, role=new_role) if m.user_id == user_id else m
            for m in self.members
        ]

        # current_role is guaranteed non-None since we checked has_member above
        self._pending_events.append(
            MemberRoleChanged(
                group_id=self.id.value,
                user_id=user_id.value,
                old_role=current_role,  # type: ignore[arg-type]
                new_role=new_role,
                occurred_at=datetime.now(UTC),
            )
        )

    def mark_for_deletion(self) -> None:
        """Mark the group for deletion and record the GroupDeleted event.

        This captures a snapshot of all current members so the outbox worker
        can clean up all SpiceDB relationships without needing external lookups.
        """
        members_snapshot = tuple(
            MemberSnapshot(user_id=m.user_id.value, role=m.role) for m in self.members
        )
        self._pending_events.append(
            GroupDeleted(
                group_id=self.id.value,
                tenant_id=self.tenant_id.value,
                members=members_snapshot,
                occurred_at=datetime.now(UTC),
            )
        )

    def has_member(self, user_id: UserId) -> bool:
        """Check if a user is a member of this group.

        Args:
            user_id: The user to check

        Returns:
            True if user is a member, False otherwise
        """
        return any(m.user_id == user_id for m in self.members)

    def get_member_role(self, user_id: UserId) -> Role | None:
        """Get the role of a member.

        Args:
            user_id: The user to get the role for

        Returns:
            The user's role, or None if not a member
        """
        for member in self.members:
            if member.user_id == user_id:
                return member.role
        return None

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


@dataclass(frozen=True)
class User:
    """User aggregate representing a person in the system.

    Users are provisioned from SSO (Red Hat SSO) and represent individuals
    who can be members of groups and access resources.

    For the walking skeleton, User is minimal (just id and username).
    Future enhancements will add email, clearance_level, etc.
    """

    id: UserId
    username: str

    def __str__(self) -> str:
        """Return string representation."""
        return f"User({self.username})"

    def __eq__(self, other: object) -> bool:
        """Users are equal if they have the same ID (identity-based equality)."""
        if not isinstance(other, User):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on ID for use in sets and dicts."""
        return hash(self.id)


@dataclass
class Tenant:
    """Tenant aggregate representing an organization in the system.

    Tenants are the top-level isolation boundary in the system.
    Each tenant represents a separate organization with its own users,
    groups, and resources.

    Business rules:
    - Tenant names must be globally unique across the system
    - Tenants are simple aggregates with no complex invariants

    Event collection:
    - All mutating operations record domain events
    - Events can be collected via collect_events() for the outbox pattern
    """

    id: TenantId
    name: str
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(cls, name: str) -> "Tenant":
        """Factory method for creating a new tenant.

        This is the proper DDD way to create aggregates. It generates the ID,
        initializes the aggregate, and records the TenantCreated event.

        Args:
            name: The name of the tenant

        Returns:
            A new Tenant aggregate with TenantCreated event recorded
        """
        tenant = cls(
            id=TenantId.generate(),
            name=name,
        )
        tenant._pending_events.append(
            TenantCreated(
                tenant_id=tenant.id.value,
                name=name,
                occurred_at=datetime.now(UTC),
            )
        )
        return tenant

    def mark_for_deletion(self) -> None:
        """Mark the tenant for deletion and record the TenantDeleted event.

        This captures the deletion event for the outbox pattern.
        Any cleanup of related resources should be handled by cascade rules
        or separate processes.
        """
        self._pending_events.append(
            TenantDeleted(
                tenant_id=self.id.value,
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
