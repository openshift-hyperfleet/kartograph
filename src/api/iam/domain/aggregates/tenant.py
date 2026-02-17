"""Tenant aggregate for IAM context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from iam.domain.exceptions import CannotRemoveLastAdminError
from iam.domain.events import (
    TenantCreated,
    TenantDeleted,
    TenantMemberAdded,
    TenantMemberRemoved,
    MemberSnapshot,
)
from iam.domain.value_objects import TenantId, TenantRole, UserId

if TYPE_CHECKING:
    from iam.domain.events import DomainEvent


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

    def get_member_role(self, user_id: UserId) -> TenantRole | None:
        """Get the current role of a user, or None if not a member.

        NOTE: This queries the in-memory state (pending events), not SpiceDB.
        For definitive answers, query SpiceDB directly.
        """
        # Check pending events for role assignments (latest wins)
        result: TenantRole | None = None
        for event in self._pending_events:
            if isinstance(event, TenantMemberAdded) and event.user_id == user_id.value:
                result = TenantRole(event.role)
            elif (
                isinstance(event, TenantMemberRemoved)
                and event.user_id == user_id.value
            ):
                result = None

        return result

    def add_member(
        self,
        user_id: UserId,
        role: TenantRole,
        added_by: Optional[UserId] = None,
        current_role: Optional[TenantRole] = None,
    ):
        """Add a user as a member to this tenant.

        Args:
            user_id: User being added
            role: Their role in the tenant
            added_by: Admin who added them (None for system/migration)
            current_role: User's current role (if any). If different from new role,
                the old role will be removed first (role replacement).
        """
        # If user already has a different role, remove it first
        if current_role is not None and current_role != role:
            self._pending_events.append(
                TenantMemberRemoved(
                    tenant_id=self.id.value,
                    user_id=user_id.value,
                    role=current_role.value,
                    removed_by=added_by.value if added_by else None,
                    occurred_at=datetime.now(UTC),
                )
            )

        self._pending_events.append(
            TenantMemberAdded(
                tenant_id=self.id.value,
                user_id=user_id.value,
                role=role.value,
                added_by=added_by.value if added_by else None,
                occurred_at=datetime.now(UTC),
            )
        )

    def remove_member(self, user_id: UserId, removed_by: UserId, is_last_admin: bool):
        """Remove a member from a tenant.

        Args:
            user_id: User being removed
            removed_by: Admin who removed them
            is_last_admin: Whether this user is the last admin in the tenant. If True,
                a CannotRemoveLastAdminError is raised.
        """
        if is_last_admin:
            raise CannotRemoveLastAdminError()

        self._pending_events.append(
            TenantMemberRemoved(
                tenant_id=self.id.value,
                user_id=user_id.value,
                occurred_at=datetime.now(UTC),
                removed_by=removed_by.value,
            )
        )

    def mark_for_deletion(self, members: list[tuple[str, str]]) -> None:
        """Mark the tenant for deletion and record the TenantDeleted event.

        This captures a snapshot of all current members so the outbox worker
        can clean up all SpiceDB relationships without needing external lookups.

        Args:
            members: List of (user_id, role) tuples for all current tenant members
        """
        members_snapshot = tuple(
            MemberSnapshot(user_id=user_id, role=role) for user_id, role in members
        )

        self._pending_events.append(
            TenantDeleted(
                tenant_id=self.id.value,
                occurred_at=datetime.now(UTC),
                members=members_snapshot,
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
