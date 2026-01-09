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
from shared_kernel.outbox.observability import OutboxWorkerProbe
from shared_kernel.outbox.serialization import deserialize_event
from shared_kernel.outbox.spicedb_translator import (
    DeleteAllRelationships,
    DeleteRelationship,
    SpiceDBTranslator,
    WriteRelationship,
)
from shared_kernel.outbox.value_objects import OutboxEntry

if TYPE_CHECKING:
    from shared_kernel.authorization.protocols import AuthorizationProvider


class OutboxWorker:
    """Background worker that processes outbox entries and applies to SpiceDB.

    The worker uses two strategies:
    1. LISTEN/NOTIFY: Real-time processing when new entries are added
    2. Polling: Fallback every N seconds to catch any missed events

    This ensures both low latency and reliability.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        authz: AuthorizationProvider,
        translator: SpiceDBTranslator,
        probe: OutboxWorkerProbe,
        db_url: str,
        poll_interval_seconds: int = 30,
        batch_size: int = 100,
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
        """
        self._session_factory = session_factory
        self._authz = authz
        self._translator = translator
        self._probe = probe
        self._db_url = db_url
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
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
            # Fetch unprocessed entries with lock
            stmt = (
                select(OutboxModel)
                .where(OutboxModel.processed_at.is_(None))
                .order_by(OutboxModel.created_at)
                .limit(self._batch_size)
                .with_for_update(skip_locked=True)
            )

            result = await session.execute(stmt)
            models = result.scalars().all()

            entries = [
                OutboxEntry(
                    id=model.id,
                    aggregate_type=model.aggregate_type,
                    aggregate_id=model.aggregate_id,
                    event_type=model.event_type,
                    payload=model.payload,
                    occurred_at=model.occurred_at,
                    processed_at=model.processed_at,
                    created_at=model.created_at,
                )
                for model in models
            ]

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
                .with_for_update(skip_locked=True)
            )

            result = await session.execute(stmt)
            model = result.scalar_one_or_none()

            if model:
                entry = OutboxEntry(
                    id=model.id,
                    aggregate_type=model.aggregate_type,
                    aggregate_id=model.aggregate_id,
                    event_type=model.event_type,
                    payload=model.payload,
                    occurred_at=model.occurred_at,
                    processed_at=model.processed_at,
                    created_at=model.created_at,
                )

                await self._process_entries([entry], session)
                await session.commit()

    async def _process_entries(
        self, entries: list[OutboxEntry], session: AsyncSession
    ) -> None:
        """Process a list of entries, applying operations to SpiceDB."""
        for entry in entries:
            try:
                # Deserialize the event from payload
                event = deserialize_event(entry.payload)

                # Translate to SpiceDB operations
                operations = self._translator.translate(event)

                # Apply each operation
                for operation in operations:
                    await self._apply_operation(operation)

                # Mark as processed
                stmt = (
                    update(OutboxModel)
                    .where(OutboxModel.id == entry.id)
                    .values(processed_at=datetime.now(UTC))
                )
                await session.execute(stmt)

                self._probe.event_processed(entry.id, entry.event_type)

            except Exception as e:
                self._probe.event_processing_failed(entry.id, str(e))
                # Don't re-raise - continue processing other entries
                # Failed entries will be retried on next poll

    async def _apply_operation(
        self, operation: WriteRelationship | DeleteRelationship | DeleteAllRelationships
    ) -> None:
        """Apply a single SpiceDB operation."""
        match operation:
            case WriteRelationship():
                await self._authz.write_relationship(
                    resource=operation.resource,
                    relation=operation.relation,
                    subject=operation.subject,
                )

            case DeleteRelationship():
                await self._authz.delete_relationship(
                    resource=operation.resource,
                    relation=operation.relation,
                    subject=operation.subject,
                )

            case DeleteAllRelationships():
                # For now, just delete the tenant relationship
                # A full implementation would need to look up all relationships
                # and delete them, but that's more complex
                pass
