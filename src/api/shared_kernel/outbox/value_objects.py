"""Value objects for the outbox pattern.

Value objects are immutable descriptors that provide type safety and
domain semantics for outbox entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class OutboxEntry:
    """Represents a single entry in the outbox table.

    This is an immutable value object that captures the state of an outbox
    entry as it exists in the database. It contains all the information
    needed to process the entry and apply it to SpiceDB.

    Attributes:
        id: Unique identifier for the entry (UUID)
        aggregate_type: Type of aggregate that generated the event (e.g., "group")
        aggregate_id: ULID of the aggregate
        event_type: Name of the domain event type (e.g., "MemberAdded")
        payload: Serialized event data as a dictionary
        occurred_at: When the domain event occurred
        processed_at: When the entry was processed (None if unprocessed)
        created_at: When the entry was created in the outbox
        retry_count: Number of times this entry has been retried
        last_error: The most recent error message (if any)
        failed_at: When the entry was moved to DLQ (None if not failed)
    """

    id: UUID
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime
    processed_at: datetime | None
    created_at: datetime
    retry_count: int = 0
    last_error: str | None = None
    failed_at: datetime | None = None

    @property
    def is_processed(self) -> bool:
        """Check if this entry has been processed.

        Returns:
            True if processed_at is set, False otherwise
        """
        return self.processed_at is not None

    @property
    def is_failed(self) -> bool:
        """Check if this entry has been moved to the DLQ.

        Returns:
            True if failed_at is set, False otherwise
        """
        return self.failed_at is not None
