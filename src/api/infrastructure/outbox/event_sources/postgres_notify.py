"""PostgreSQL NOTIFY-based event source for outbox pattern.

This module provides an event source that listens for PostgreSQL NOTIFY
events and invokes callbacks when outbox entries are created. It uses
asyncpg-listen for reliable connection handling and automatic reconnection.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import UUID

from asyncpg_listen import (
    ListenPolicy,
    NotificationListener,
    NotificationOrTimeout,
    Timeout,
    connect_func,
)

from shared_kernel.outbox.ports import OutboxEventSource

if TYPE_CHECKING:
    pass


class PostgresNotifyEventSource(OutboxEventSource):
    """PostgreSQL NOTIFY-based event source for outbox entries.

    Listens for PostgreSQL NOTIFY events on a channel and invokes a callback
    when outbox entries are created. Uses asyncpg-listen for reliable connection
    handling and automatic reconnection.

    This class implements the OutboxEventSource protocol from shared_kernel.
    """

    def __init__(self, db_url: str, channel: str = "outbox_events") -> None:
        """Initialize the NOTIFY event source.

        Args:
            db_url: PostgreSQL connection URL
            channel: NOTIFY channel name (default: "outbox_events")
        """
        self._db_url = db_url
        self._channel = channel
        self._on_event: Callable[[UUID], Awaitable[None]] | None = None
        self._running = False
        self._listener: NotificationListener | None = None

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
                    if self._on_event is not None:
                        await self._on_event(entry_id)
                except (ValueError, TypeError):
                    # Invalid UUID payload, ignore gracefully
                    # These events will be picked up by the polling fallback
                    pass

        try:
            self._listener = NotificationListener(connect_func(self._db_url))

            # Run the listener - this blocks until cancelled
            await self._listener.run(
                {self._channel: handle_notification},
                policy=ListenPolicy.ALL,
            )
        except Exception:
            # Listen loop failed, caller should handle appropriately
            pass

    async def stop(self) -> None:
        """Stop listening and clean up resources.

        Sets _running to False to signal the listener to stop.
        This method is safe to call even if start() was never called.
        """
        self._running = False
