"""Ingestion event serializer for the outbox.

Serializes and deserializes Ingestion domain events (JobPackageProduced,
IngestionFailed) for storage in the outbox table.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, get_args

from ingestion.domain.events import DomainEvent

# Derive supported events from the DomainEvent type alias
_SUPPORTED_EVENTS: frozenset[str] = frozenset(
    cls.__name__ for cls in get_args(DomainEvent)
)

# Build registry mapping event type names to classes
_EVENT_REGISTRY: dict[str, type] = {cls.__name__: cls for cls in get_args(DomainEvent)}


class IngestionEventSerializer:
    """Serializes and deserializes Ingestion domain events.

    Handles JobPackageProduced and IngestionFailed events.
    All fields are JSON-serializable except datetime (occurred_at).
    """

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this serializer handles."""
        return _SUPPORTED_EVENTS

    def serialize(self, event: DomainEvent) -> dict[str, Any]:
        """Convert a domain event to a JSON-serializable dictionary.

        Args:
            event: The domain event to serialize

        Returns:
            Dictionary with all event fields

        Raises:
            ValueError: If the event type is not supported
        """
        event_type = type(event).__name__
        if event_type not in _SUPPORTED_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")

        data = asdict(event)
        # Convert datetime fields to ISO strings
        for key, value in list(data.items()):
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data

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
        event_class = _EVENT_REGISTRY.get(event_type)
        if event_class is None:
            raise ValueError(f"Unsupported event type: {event_type}")

        data = payload.copy()
        if "occurred_at" in data:
            data["occurred_at"] = datetime.fromisoformat(data["occurred_at"])

        return event_class(**data)
