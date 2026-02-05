"""Event sources for outbox pattern.

Event sources implement different mechanisms for being notified of new
outbox entries. Each source monitors for events and invokes callbacks
when entries are created.
"""

from infrastructure.outbox.event_sources.postgres_notify import (
    PostgresNotifyEventSource,
)

__all__ = ["PostgresNotifyEventSource"]
