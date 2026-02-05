"""Protocols (ports) for the outbox pattern.

These protocols define the interfaces for outbox operations. They enable
a plugin architecture where each bounded context can register its own
event translators and serializers without shared_kernel knowing about them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from shared_kernel.outbox.operations import SpiceDBOperation
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
        self,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
        aggregate_type: str,
        aggregate_id: str,
    ) -> None:
        """Append a pre-serialized event to the outbox within the current transaction.

        This method should be called after the aggregate is persisted but
        before the transaction is committed. The event will be stored in
        the outbox table and processed asynchronously by the worker.

        Args:
            event_type: Name of the domain event type (e.g., "GroupCreated")
            payload: Pre-serialized event data as a dictionary
            occurred_at: When the domain event occurred
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


@runtime_checkable
class EventTranslator(Protocol):
    """Translates domain events to SpiceDB operations.

    Each bounded context provides its own implementation that knows how to
    translate its domain events to the appropriate SpiceDB relationship
    operations. This keeps shared_kernel agnostic of specific domain events.
    """

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this translator handles.

        Returns:
            Frozenset of event type names (e.g., {"GroupCreated", "MemberAdded"})
        """
        ...

    def translate(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list["SpiceDBOperation"]:
        """Convert an event payload to SpiceDB operations.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Returns:
            List of SpiceDB operations to execute

        Raises:
            ValueError: If the event type is not supported
        """
        ...


@runtime_checkable
class EventSerializer(Protocol):
    """Serializes and deserializes domain events.

    Each bounded context provides its own implementation that knows how to
    serialize its domain events to JSON-compatible dictionaries and
    deserialize them back. This keeps shared_kernel agnostic of specific
    domain event structures.
    """

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this serializer handles.

        Returns:
            Frozenset of event type names (e.g., {"GroupCreated", "MemberAdded"})
        """
        ...

    def serialize(self, event: Any) -> dict[str, Any]:
        """Convert a domain event to a JSON-serializable dictionary.

        Args:
            event: The domain event to serialize

        Returns:
            Dictionary with all event fields

        Raises:
            ValueError: If the event type is not supported
        """
        ...

    def deserialize(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> Any:
        """Reconstruct a domain event from a payload.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Returns:
            The reconstructed domain event

        Raises:
            ValueError: If the event type is not supported
        """
        ...


@runtime_checkable
class OutboxEventSource(Protocol):
    """Event source for outbox entries.

    Implementations provide different mechanisms for being notified of new
    outbox entries (PostgreSQL NOTIFY, polling, message queue, etc.).

    The event source operates in a push model: when started, it monitors
    for new outbox entries and invokes the provided callback for each one.
    """

    async def start(self, on_event: Callable[[UUID], Awaitable[None]]) -> None:
        """Start the event source and begin monitoring for events.

        The event source should invoke the callback when new outbox entries
        are created, passing the entry UUID. The callback is async and should
        be awaited.

        This method should not return until stop() is called or an error occurs.

        Args:
            on_event: Async callback to invoke when an event occurs, passing entry UUID
        """
        ...

    async def stop(self) -> None:
        """Stop the event source and clean up resources.

        This should gracefully shut down the monitoring mechanism and
        release any held resources (connections, file handles, etc.).
        """
        ...
