"""Outbox worker for processing events and writing to SpiceDB.

The worker runs as a background task within the FastAPI application,
listening for PostgreSQL NOTIFY events and processing outbox entries.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.outbox.models import OutboxModel
from shared_kernel.outbox.operations import DeleteRelationship, WriteRelationship
from shared_kernel.outbox.ports import EventTranslator
from shared_kernel.outbox.value_objects import OutboxEntry

if TYPE_CHECKING:
    from shared_kernel.authorization.protocols import AuthorizationProvider
    from shared_kernel.outbox.observability import OutboxWorkerProbe


class OutboxWorker:
    """Background worker that processes outbox entries and applies to SpiceDB.

    The worker uses two strategies:
    1. LISTEN/NOTIFY: Real-time processing when new entries are added
    2. Polling: Fallback every N seconds to catch any missed events

    This ensures both low latency and reliability.

    The worker uses a plugin architecture for event translation:
    - Translators are injected and handle converting events to SpiceDB operations
    - This keeps the worker generic and bounded-context agnostic
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        authz: AuthorizationProvider,
        translator: EventTranslator,
        probe: OutboxWorkerProbe,
        db_url: str,
        poll_interval_seconds: int = 30,
        batch_size: int = 100,
        max_retries: int = 5,
    ) -> None:
        """Initialize the worker.

        Args:
            session_factory: Factory for creating database sessions
            authz: Authorization provider for SpiceDB operations
            translator: Translator for domain events to SpiceDB operations
            probe: Observability probe for logging/metrics
            db_url: PostgreSQL connection URL for LISTEN
            poll_interval_seconds: How often to poll for missed events
            batch_size: Maximum entries to process per batch
            max_retries: Maximum retry attempts before moving to DLQ
        """
        self._session_factory = session_factory
        self._authz = authz
        self._translator = translator
        self._probe = probe
        self._db_url = db_url
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the worker processing loops.

        Starts both the LISTEN loop (for real-time processing) and
        the poll loop (for catching missed events).
        """
        self._running = True
        self._probe.worker_started()

        # Start poll loop (always runs as fallback)
        poll_task = asyncio.create_task(self._poll_loop())
        self._tasks.append(poll_task)

        # Start listen loop (for real-time processing)
        # Note: Listen loop is optional and may fail if DB doesn't support it
        try:
            listen_task = asyncio.create_task(self._listen_loop())
            self._tasks.append(listen_task)
        except Exception:
            # Listen loop is optional, poll loop is the fallback
            pass

    async def stop(self) -> None:
        """Gracefully stop the worker.

        Signals all loops to stop and waits for them to complete.
        """
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()
        self._probe.worker_stopped()

    async def _listen_loop(self) -> None:
        """Listen for PostgreSQL NOTIFY and process immediately.

        Uses asyncpg-listen for reliable connection handling.
        """
        from asyncpg_listen import (
            ListenPolicy,
            NotificationListener,
            NotificationOrTimeout,
            Timeout,
            connect_func,
        )

        self._probe.listen_loop_started()

        async def handle_notification(
            notification: NotificationOrTimeout,
        ) -> None:
            """Handler for outbox_events notifications."""
            if not self._running:
                return

            # Skip timeouts
            if isinstance(notification, Timeout):
                return

            # Process the notification payload
            if notification.payload:
                try:
                    entry_id = UUID(notification.payload)
                    await self._process_single(entry_id)
                except (ValueError, Exception):
                    # Invalid UUID or processing error, will be picked up by poll
                    pass

        try:
            listener = NotificationListener(connect_func(self._db_url))

            # Run the listener - this blocks until cancelled
            await listener.run(
                {"outbox_events": handle_notification},
                policy=ListenPolicy.ALL,
                notification_timeout=self._poll_interval,
            )

        except asyncio.CancelledError:
            pass
        except Exception:
            # Listen loop failed, poll loop will handle entries
            pass

    async def _poll_loop(self) -> None:
        """Fallback polling for missed events.

        Runs every poll_interval_seconds to process any unprocessed entries.
        """
        self._probe.poll_loop_started()

        while self._running:
            try:
                await self._process_batch()
            except Exception:
                # Log error but continue polling
                pass

            await asyncio.sleep(self._poll_interval)

    async def _process_batch(self) -> None:
        """Fetch and process a batch of unprocessed entries."""
        async with self._session_factory() as session:
            # Fetch unprocessed entries with lock (excluding failed entries)
            stmt = (
                select(OutboxModel)
                .where(OutboxModel.processed_at.is_(None))
                .where(OutboxModel.failed_at.is_(None))
                .order_by(OutboxModel.created_at)
                .limit(self._batch_size)
                .with_for_update(skip_locked=True)
            )

            result = await session.execute(stmt)
            models = result.scalars().all()

            entries = [self._model_to_entry(model) for model in models]

            if entries:
                await self._process_entries(entries, session)
                await session.commit()
                self._probe.batch_processed(len(entries))

    async def _process_single(self, entry_id: UUID) -> None:
        """Process a single entry by ID (from NOTIFY)."""
        async with self._session_factory() as session:
            stmt = (
                select(OutboxModel)
                .where(OutboxModel.id == entry_id)
                .where(OutboxModel.processed_at.is_(None))
                .where(OutboxModel.failed_at.is_(None))
                .with_for_update(skip_locked=True)
            )

            result = await session.execute(stmt)
            model = result.scalar_one_or_none()

            if model:
                entry = self._model_to_entry(model)
                await self._process_entries([entry], session)
                await session.commit()

    async def _process_entries(
        self,
        entries: list[OutboxEntry],
        session: AsyncSession,
    ) -> None:
        """Process a list of entries, applying operations to SpiceDB."""
        for entry in entries:
            try:
                # Translate to SpiceDB operations using the injected translator
                operations = self._translator.translate(entry.event_type, entry.payload)

                # Apply each operation
                for operation in operations:
                    await self._apply_operation(operation)

                # Mark as processed
                await self._mark_processed(entry.id, session)
                self._probe.event_processed(entry.id, entry.event_type)

            except Exception as e:
                await self._handle_processing_failure(entry, str(e), session)

    async def _apply_operation(
        self,
        operation: WriteRelationship | DeleteRelationship,
    ) -> None:
        """Apply a single SpiceDB operation."""
        match operation:
            case WriteRelationship():
                await self._authz.write_relationship(
                    resource=operation.resource,
                    relation=operation.relation_name,
                    subject=operation.subject,
                )

            case DeleteRelationship():
                await self._authz.delete_relationship(
                    resource=operation.resource,
                    relation=operation.relation_name,
                    subject=operation.subject,
                )

    async def _mark_processed(self, entry_id: UUID, session: AsyncSession) -> None:
        """Mark an entry as successfully processed."""
        stmt = (
            update(OutboxModel)
            .where(OutboxModel.id == entry_id)
            .values(processed_at=datetime.now(UTC))
        )
        await session.execute(stmt)

    async def _handle_processing_failure(
        self,
        entry: OutboxEntry,
        error: str,
        session: AsyncSession,
    ) -> None:
        """Handle a processing failure, with retry or DLQ.

        Increments retry count and either schedules for retry or moves
        to the dead letter queue if max retries exceeded.

        Args:
            entry: The outbox entry that failed
            error: The error message
            session: The database session
        """
        new_retry_count = entry.retry_count + 1

        if new_retry_count >= self._max_retries:
            await self._move_to_dlq(entry.id, new_retry_count, error, session)
            self._probe.event_moved_to_dlq(entry.id, entry.event_type, error)
        else:
            await self._increment_retry(entry.id, new_retry_count, error, session)
            self._probe.event_processing_failed(entry.id, error, new_retry_count)

    async def _move_to_dlq(
        self,
        entry_id: UUID,
        retry_count: int,
        error: str,
        session: AsyncSession,
    ) -> None:
        """Move an entry to the dead letter queue.

        Sets failed_at to mark the entry as permanently failed.
        The entry will no longer be picked up by polling.

        Args:
            entry_id: The entry to move to DLQ
            retry_count: The final retry count
            error: The error that caused the failure
            session: The database session
        """
        stmt = (
            update(OutboxModel)
            .where(OutboxModel.id == entry_id)
            .values(
                retry_count=retry_count,
                last_error=error,
                failed_at=datetime.now(UTC),
            )
        )
        await session.execute(stmt)

    async def _increment_retry(
        self,
        entry_id: UUID,
        retry_count: int,
        error: str,
        session: AsyncSession,
    ) -> None:
        """Increment retry count for an entry.

        The entry will be retried on the next poll cycle.

        Args:
            entry_id: The entry to update
            retry_count: The new retry count
            error: The error that caused the failure
            session: The database session
        """
        stmt = (
            update(OutboxModel)
            .where(OutboxModel.id == entry_id)
            .values(
                retry_count=retry_count,
                last_error=error,
            )
        )
        await session.execute(stmt)

    def _model_to_entry(self, model: OutboxModel) -> OutboxEntry:
        """Convert an OutboxModel to an OutboxEntry value object."""
        return OutboxEntry(
            id=model.id,
            aggregate_type=model.aggregate_type,
            aggregate_id=model.aggregate_id,
            event_type=model.event_type,
            payload=model.payload,
            occurred_at=model.occurred_at,
            processed_at=model.processed_at,
            created_at=model.created_at,
            retry_count=model.retry_count,
            last_error=model.last_error,
            failed_at=model.failed_at,
        )
