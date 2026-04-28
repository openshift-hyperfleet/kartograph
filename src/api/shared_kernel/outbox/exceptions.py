"""Domain exceptions for the outbox pattern.

These exceptions represent permanent, non-transient failures in outbox
processing that must be handled differently from transient errors.

Key distinction:
- Transient errors (e.g., network timeout, SpiceDB unavailable): retry with
  exponential back-off, eventually dead-letter after max_retries.
- Permanent errors (e.g., unknown event type): immediately dead-letter without
  any retry, because retrying would never succeed.
"""

from __future__ import annotations


class UnknownEventTypeError(Exception):
    """Raised when an event type has no registered handler.

    This is a *permanent* failure — retrying will never produce a different
    result because the event type simply has no handler registered. The outbox
    worker should immediately move the entry to the dead-letter queue rather
    than incrementing its retry count.

    Attributes:
        event_type: The unrecognised event type that was encountered.
        registered_types: The set of event types that ARE registered,
            included to aid diagnosis of misconfiguration.
    """

    def __init__(self, event_type: str, registered_types: frozenset[str]) -> None:
        self.event_type = event_type
        self.registered_types = registered_types
        super().__init__(
            f"No handler registered for event type '{event_type}'. "
            f"Registered types: {sorted(registered_types)}"
        )
