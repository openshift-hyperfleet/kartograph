"""Composite event handler for the outbox pattern.

This module provides the CompositeEventHandler which aggregates multiple
event handlers, dispatching events to all registered handlers for a given
event type (fan-out). This enables the plugin architecture where each
bounded context registers its own handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared_kernel.outbox.ports import EventHandler

if TYPE_CHECKING:
    from shared_kernel.outbox.observability import OutboxWorkerProbe


class CompositeEventHandler:
    """Dispatches events to multiple registered handlers (fan-out).

    This class implements the EventHandler protocol by aggregating
    multiple handlers and routing events to all handlers registered
    for each event type. One event type can have multiple handlers.
    """

    def __init__(self, probe: OutboxWorkerProbe | None = None) -> None:
        """Initialize with empty handler registry.

        Args:
            probe: Optional observability probe for logging registrations
                   and dispatch events
        """
        self._handlers_by_type: dict[str, list[EventHandler]] = {}
        self._probe = probe

    def register(self, handler: EventHandler, handler_name: str | None = None) -> None:
        """Register an event handler for its supported event types.

        A handler is added to the dispatch list for each event type it
        supports. Multiple handlers can be registered for the same
        event type to achieve fan-out.

        Args:
            handler: The handler to register
            handler_name: Optional name for logging (defaults to class name)
        """
        event_types = handler.supported_event_types()

        for event_type in event_types:
            if event_type not in self._handlers_by_type:
                self._handlers_by_type[event_type] = []
            if handler not in self._handlers_by_type[event_type]:
                self._handlers_by_type[event_type].append(handler)

        # Log registration if probe is available
        if self._probe is not None:
            name = handler_name if handler_name is not None else type(handler).__name__
            self._probe.handler_registered(name, event_types)

    def supported_event_types(self) -> frozenset[str]:
        """Return all supported event types across all registered handlers."""
        return frozenset(self._handlers_by_type.keys())

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Dispatch an event to all registered handlers for that type.

        Handlers are called in registration order. If no handlers are
        registered for the event type, raises ValueError.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Raises:
            ValueError: If no handler is registered for the event type
        """
        handlers = self._handlers_by_type.get(event_type)
        if handlers is None:
            raise ValueError(
                f"No handler registered for event type: {event_type}. "
                f"Registered types: {sorted(self._handlers_by_type.keys())}"
            )

        for handler in handlers:
            await handler.handle(event_type, payload)
