"""Tenant aggregate for IAM context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from iam.domain.events import TenantCreated, TenantDeleted, TenantMemberAdded
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

    def add_user(
        self, user_id: UserId, role: TenantRole, added_by: Optional[UserId] = None
    ):
        """Add a user as a member to this tenant.

        Args:
            user_id: User being added
            role: Their role in the tenant
            added_by: Admin who added them (None for system/migration)
        """
        self._pending_events.append(
            TenantMemberAdded(
                tenant_id=self.id,
                user_id=user_id,
                role=role,
                added_by=added_by,
                occurred_at=datetime.now(UTC),
            )
        )

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
