"""PostgreSQL NOTIFY-based event source for outbox pattern.

This module provides an event source that listens for PostgreSQL NOTIFY
events and invokes callbacks when outbox entries are created. It uses
asyncpg-listen for reliable connection handling and automatic reconnection.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from asyncpg_listen import (
    ListenPolicy,
    NotificationListener,
    NotificationOrTimeout,
    Timeout,
    connect_func,
)

from shared_kernel.outbox.observability import (
    DefaultEventSourceProbe,
    EventSourceProbe,
)
from shared_kernel.outbox.ports import OutboxEventSource


class PostgresNotifyEventSource(OutboxEventSource):
    """PostgreSQL NOTIFY-based event source for outbox entries.

    Listens for PostgreSQL NOTIFY events on a channel and invokes a callback
    when outbox entries are created. Uses asyncpg-listen for reliable connection
    handling and automatic reconnection.

    This class implements the OutboxEventSource protocol from shared_kernel.
    """

    def __init__(
        self,
        db_url: str,
        channel: str = "outbox_events",
        probe: EventSourceProbe | None = None,
    ) -> None:
        """Initialize the NOTIFY event source.

        Args:
            db_url: PostgreSQL connection URL
            channel: NOTIFY channel name (default: "outbox_events")
            probe: Optional observability probe (default: DefaultEventSourceProbe)
        """
        self._db_url = db_url
        self._channel = channel
        self._probe = probe or DefaultEventSourceProbe()
        self._on_event: Callable[[UUID], Awaitable[None]] | None = None
        self._running = False
        self._listener: NotificationListener | None = None
        self._listener_task: asyncio.Task[None] | None = None

    async def start(self, on_event: Callable[[UUID], Awaitable[None]]) -> None:
        """Start listening for NOTIFY events.

        This method blocks until stop() is called. It creates a NotificationListener
        and processes NOTIFY events, invoking the callback for each valid UUID.

        Args:
            on_event: Async callback to invoke when an event occurs
        """
        self._on_event = on_event
        self._running = True

        async def handle_notification(
            notification: NotificationOrTimeout,
        ) -> None:
            """Handler for outbox_events notifications."""
            if not self._running:
                return

            # Skip timeouts - asyncpg-listen sends Timeout when no notification
            # is received within the timeout period
            if isinstance(notification, Timeout):
                return

            # Process the notification payload
            if notification.payload:
                try:
                    entry_id = UUID(notification.payload)
                    self._probe.notification_received(entry_id)
                    if self._on_event is not None:
                        await self._on_event(entry_id)
                except (ValueError, TypeError):
                    # Invalid UUID payload, ignore gracefully
                    # These events will be picked up by the polling fallback
                    self._probe.invalid_notification_ignored(
                        notification.payload, "Invalid UUID format"
                    )

        try:
            self._listener = NotificationListener(connect_func(self._db_url))
            self._probe.event_source_started(self._channel)

            # Run the listener - this blocks until cancelled
            self._listener_task = asyncio.create_task(
                self._listener.run(
                    {self._channel: handle_notification},
                    policy=ListenPolicy.ALL,
                )
            )
            await self._listener_task
        except asyncio.CancelledError:
            # Task was cancelled via stop(), this is expected
            pass
        except Exception as e:
            # Listen loop failed, caller should handle appropriately
            self._probe.listener_error(str(e))

    async def stop(self) -> None:
        """Stop the event source and clean up resources."""
        self._running = False

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        self._probe.event_source_stopped()
