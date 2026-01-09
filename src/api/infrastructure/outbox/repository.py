"""Outbox repository implementation.

This module provides the PostgreSQL implementation of the outbox repository.
It handles persisting domain events to the outbox table for later processing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.outbox.models import OutboxModel
from shared_kernel.outbox.value_objects import OutboxEntry  # noqa: F401 - used in type hints

if TYPE_CHECKING:
    from shared_kernel.outbox.ports import EventSerializer


class OutboxRepository:
    """PostgreSQL implementation of the outbox repository.

    This repository shares the same database session as the calling service,
    ensuring that event appends happen within the same transaction as the
    aggregate changes. This is critical for the atomicity guarantee of the
    outbox pattern.

    The repository only calls session.add() and session.execute() - it never
    calls session.commit(). The calling service owns the transaction boundary.
    """

    def __init__(
        self,
        session: AsyncSession,
        serializer: "EventSerializer",
    ) -> None:
        """Initialize the repository with a session and serializer.

        Args:
            session: The SQLAlchemy async session (shared with calling service)
            serializer: The event serializer for converting events to payloads
        """
        self._session = session
        self._serializer = serializer

    async def append(self, event: Any, aggregate_type: str, aggregate_id: str) -> None:
        """Append an event to the outbox within the current transaction.

        This method creates an OutboxModel and adds it to the session.
        The event is serialized to a JSON payload. The transaction is not
        committed - that is the responsibility of the calling service.

        Args:
            event: The domain event to append
            aggregate_type: Type of aggregate (e.g., "group")
            aggregate_id: ULID of the aggregate
        """
        payload = self._serializer.serialize(event)

        model = OutboxModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=type(event).__name__,
            payload=payload,
            occurred_at=event.occurred_at,
            processed_at=None,
        )

        self._session.add(model)

    async def fetch_unprocessed(self, limit: int = 100) -> list[OutboxEntry]:
        """Fetch unprocessed entries ordered by creation time.

        Uses FOR UPDATE SKIP LOCKED for safe concurrent access when multiple
        workers are running. This ensures that each worker processes different
        entries and no entry is processed twice concurrently.

        Args:
            limit: Maximum number of entries to fetch

        Returns:
            List of unprocessed OutboxEntry value objects
        """
        stmt = (
            select(OutboxModel)
            .where(OutboxModel.processed_at.is_(None))
            .where(OutboxModel.failed_at.is_(None))
            .order_by(OutboxModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [model.to_value_object() for model in models]

    async def mark_processed(self, entry_id: UUID) -> None:
        """Mark an entry as processed.

        Sets the processed_at timestamp to the current UTC time.

        Args:
            entry_id: The UUID of the entry to mark as processed
        """
        stmt = (
            update(OutboxModel)
            .where(OutboxModel.id == entry_id)
            .values(processed_at=datetime.now(UTC))
        )

        await self._session.execute(stmt)
