"""Event serialization for the outbox pattern.

This module provides functions to serialize domain events to JSON-compatible
dictionaries and deserialize them back to domain event objects.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from iam.domain.events import (
    DomainEvent,
    GroupCreated,
    GroupDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
)
from iam.domain.value_objects import Role

# Registry of event types for deserialization
EVENT_REGISTRY: dict[str, type[DomainEvent]] = {
    "GroupCreated": GroupCreated,
    "GroupDeleted": GroupDeleted,
    "MemberAdded": MemberAdded,
    "MemberRemoved": MemberRemoved,
    "MemberRoleChanged": MemberRoleChanged,
}


def serialize_event(event: DomainEvent) -> dict[str, Any]:
    """Convert a domain event to a JSON-serializable dictionary.

    Args:
        event: The domain event to serialize

    Returns:
        A dictionary with all event fields and a __type__ key for the event type
    """
    # Convert dataclass to dict
    data = asdict(event)

    # Add type information for deserialization
    data["__type__"] = type(event).__name__

    # Convert non-JSON-serializable types
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, Role):
            data[key] = value.value

    return data


def deserialize_event(payload: dict[str, Any]) -> DomainEvent:
    """Reconstruct a domain event from a dictionary.

    Args:
        payload: The serialized event data with a __type__ key

    Returns:
        The reconstructed domain event

    Raises:
        KeyError: If __type__ is missing from payload
        ValueError: If the event type is unknown
    """
    # Extract and remove type information
    event_type = payload["__type__"]
    data = {k: v for k, v in payload.items() if k != "__type__"}

    # Get the event class from registry
    event_class = EVENT_REGISTRY.get(event_type)
    if event_class is None:
        raise ValueError(f"Unknown event type: {event_type}")

    # Convert serialized types back to their original types
    for key, value in data.items():
        if key == "occurred_at":
            data[key] = datetime.fromisoformat(value)
        elif key in ("role", "old_role", "new_role"):
            data[key] = Role(value)

    return event_class(**data)
