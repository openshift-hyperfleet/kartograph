"""Repository protocols (ports) for the outbox pattern.

These protocols define the interface for outbox operations. Implementations
handle the actual persistence to PostgreSQL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from iam.domain.events import DomainEvent
    from shared_kernel.outbox.value_objects import OutboxEntry


@runtime_checkable
class IOutboxRepository(Protocol):
    """Repository for outbox entry persistence.

    This protocol defines the interface for appending domain events to the
    outbox table and processing them asynchronously.

    The repository shares the same database session as the calling service,
    ensuring that event appends happen within the same transaction as the
    aggregate changes.
    """

    async def append(
        self, event: "DomainEvent", aggregate_type: str, aggregate_id: str
    ) -> None:
        """Append an event to the outbox within the current transaction.

        This method should be called after the aggregate is persisted but
        before the transaction is committed. The event will be stored in
        the outbox table and processed asynchronously by the worker.

        Args:
            event: The domain event to append
            aggregate_type: Type of aggregate (e.g., "group")
            aggregate_id: ULID of the aggregate
        """
        ...

    async def fetch_unprocessed(self, limit: int = 100) -> list["OutboxEntry"]:
        """Fetch unprocessed entries ordered by creation time.

        Uses FOR UPDATE SKIP LOCKED for safe concurrent access when multiple
        workers are running.

        Args:
            limit: Maximum number of entries to fetch

        Returns:
            List of unprocessed OutboxEntry objects
        """
        ...

    async def mark_processed(self, entry_id: UUID) -> None:
        """Mark an entry as processed.

        Sets the processed_at timestamp to the current time.

        Args:
            entry_id: The UUID of the entry to mark as processed
        """
        ...
