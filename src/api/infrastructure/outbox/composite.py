"""Composite handlers for the outbox pattern.

These classes aggregate multiple context-specific translators and serializers,
delegating to the appropriate handler based on event type. This enables
the plugin architecture where each bounded context registers its own handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared_kernel.outbox.operations import SpiceDBOperation
from shared_kernel.outbox.ports import EventSerializer, EventTranslator

if TYPE_CHECKING:
    from shared_kernel.outbox.observability import OutboxWorkerProbe


class CompositeTranslator:
    """Delegates translation to context-specific translators.

    This class implements the EventTranslator protocol by aggregating
    multiple translators and routing to the appropriate one based on
    the event type.
    """

    def __init__(self, probe: "OutboxWorkerProbe | None" = None) -> None:
        """Initialize with empty translator list.

        Args:
            probe: Optional observability probe for logging registrations
        """
        self._translators: list[EventTranslator] = []
        self._type_cache: dict[str, EventTranslator] = {}
        self._probe = probe

    def register(
        self, translator: EventTranslator, context_name: str | None = None
    ) -> None:
        """Register a context-specific translator.

        Args:
            translator: The translator to register
            context_name: Optional bounded context name (defaults to class name)
        """
        self._translators.append(translator)
        event_types = translator.supported_event_types()

        # Update cache for fast lookup
        for event_type in event_types:
            self._type_cache[event_type] = translator

        # Log registration if probe is available
        if self._probe is not None:
            name = (
                context_name if context_name is not None else type(translator).__name__
            )
            self._probe.translator_registered(name, event_types)

    def supported_event_types(self) -> frozenset[str]:
        """Return all supported event types across all translators."""
        all_types: set[str] = set()
        for translator in self._translators:
            all_types.update(translator.supported_event_types())
        return frozenset(all_types)

    def translate(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate an event to SpiceDB operations.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Returns:
            List of SpiceDB operations to execute

        Raises:
            ValueError: If no translator is registered for the event type
        """
        translator = self._type_cache.get(event_type)
        if translator is None:
            raise ValueError(
                f"No translator registered for event type: {event_type}. "
                f"Registered types: {sorted(self._type_cache.keys())}"
            )
        return translator.translate(event_type, payload)


class CompositeSerializer:
    """Delegates serialization to context-specific serializers.

    This class implements the EventSerializer protocol by aggregating
    multiple serializers and routing to the appropriate one based on
    the event type.
    """

    def __init__(self) -> None:
        """Initialize with empty serializer list."""
        self._serializers: list[EventSerializer] = []
        self._type_cache: dict[str, EventSerializer] = {}

    def register(self, serializer: EventSerializer) -> None:
        """Register a context-specific serializer.

        Args:
            serializer: The serializer to register
        """
        self._serializers.append(serializer)
        # Update cache for fast lookup
        for event_type in serializer.supported_event_types():
            self._type_cache[event_type] = serializer

    def supported_event_types(self) -> frozenset[str]:
        """Return all supported event types across all serializers."""
        all_types: set[str] = set()
        for serializer in self._serializers:
            all_types.update(serializer.supported_event_types())
        return frozenset(all_types)

    def serialize(self, event: Any) -> dict[str, Any]:
        """Serialize a domain event to a dictionary.

        Args:
            event: The domain event to serialize

        Returns:
            Dictionary with all event fields

        Raises:
            ValueError: If no serializer is registered for the event type
        """
        event_type = type(event).__name__
        serializer = self._type_cache.get(event_type)
        if serializer is None:
            raise ValueError(
                f"No serializer registered for event type: {event_type}. "
                f"Registered types: {sorted(self._type_cache.keys())}"
            )
        return serializer.serialize(event)

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
            ValueError: If no serializer is registered for the event type
        """
        serializer = self._type_cache.get(event_type)
        if serializer is None:
            raise ValueError(
                f"No serializer registered for event type: {event_type}. "
                f"Registered types: {sorted(self._type_cache.keys())}"
            )
        return serializer.deserialize(event_type, payload)
