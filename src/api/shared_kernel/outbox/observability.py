"""Observability probes for the outbox worker.

Following Domain Oriented Observability, probes capture domain-significant
events and metrics without cluttering business logic with logging concerns.
"""

from __future__ import annotations

import structlog
from typing import Protocol
from uuid import UUID


logger = structlog.get_logger()


class OutboxWorkerProbe(Protocol):
    """Protocol for outbox worker observability.

    Implementations can log, emit metrics, or send traces.
    """

    def worker_started(self) -> None:
        """Called when the worker starts."""
        ...

    def worker_stopped(self) -> None:
        """Called when the worker stops."""
        ...

    def event_processed(self, entry_id: UUID, event_type: str) -> None:
        """Called when an event is successfully processed."""
        ...

    def event_processing_failed(
        self, entry_id: UUID, error: str, retry_count: int
    ) -> None:
        """Called when event processing fails and will be retried."""
        ...

    def event_moved_to_dlq(self, entry_id: UUID, event_type: str, error: str) -> None:
        """Called when an event exceeds max retries and is moved to DLQ."""
        ...

    def batch_processed(self, count: int) -> None:
        """Called when a batch of events is processed."""
        ...

    def listen_loop_started(self) -> None:
        """Called when the LISTEN loop starts."""
        ...

    def poll_loop_started(self) -> None:
        """Called when the poll loop starts."""
        ...

    def poll_loop_error(self, error: str) -> None:
        """Called when an error occurs in the poll loop."""
        ...

    def event_translated(
        self, entry_id: UUID, event_type: str, operation_count: int
    ) -> None:
        """Called when an event is translated to SpiceDB operations.

        Provides visibility into how many operations each event produces.
        Zero operations may indicate misconfiguration or unsupported event type.
        """
        ...

    def translator_registered(
        self, context_name: str, event_types: frozenset[str]
    ) -> None:
        """Called when a translator plugin is registered.

        Provides visibility into which bounded contexts have registered
        their event translators and what event types they handle.
        """
        ...


class DefaultOutboxWorkerProbe:
    """Default implementation using structlog.

    Logs all worker events with appropriate log levels.
    """

    def __init__(self) -> None:
        """Initialize the probe with a logger."""
        self._log = logger.bind(component="outbox_worker")

    def worker_started(self) -> None:
        """Log worker start."""
        self._log.info("outbox_worker_started")

    def worker_stopped(self) -> None:
        """Log worker stop."""
        self._log.info("outbox_worker_stopped")

    def event_processed(self, entry_id: UUID, event_type: str) -> None:
        """Log successful event processing."""
        self._log.info(
            "outbox_event_processed",
            entry_id=str(entry_id),
            event_type=event_type,
        )

    def event_processing_failed(
        self, entry_id: UUID, error: str, retry_count: int
    ) -> None:
        """Log failed event processing that will be retried."""
        self._log.warning(
            "outbox_event_processing_failed",
            entry_id=str(entry_id),
            error=error,
            retry_count=retry_count,
        )

    def event_moved_to_dlq(self, entry_id: UUID, event_type: str, error: str) -> None:
        """Log event moved to dead letter queue."""
        self._log.error(
            "outbox_event_moved_to_dlq",
            entry_id=str(entry_id),
            event_type=event_type,
            error=error,
        )

    def batch_processed(self, count: int) -> None:
        """Log batch processing."""
        if count > 0:
            self._log.info("outbox_batch_processed", count=count)

    def listen_loop_started(self) -> None:
        """Log LISTEN loop start."""
        self._log.info("outbox_listen_loop_started")

    def poll_loop_started(self) -> None:
        """Log poll loop start."""
        self._log.info("outbox_poll_loop_started")

    def poll_loop_error(self, error: str) -> None:
        """Log poll loop error."""
        self._log.warning("outbox_poll_loop_error", error=error)

    def event_translated(
        self, entry_id: UUID, event_type: str, operation_count: int
    ) -> None:
        """Log event translation with operation count.

        Zero operations is valid for audit-only events (e.g., TenantCreated,
        TenantDeleted) that don't require side effects like SpiceDB writes.
        """
        self._log.debug(
            "outbox_event_translated",
            entry_id=str(entry_id),
            event_type=event_type,
            operation_count=operation_count,
        )

    def translator_registered(
        self, context_name: str, event_types: frozenset[str]
    ) -> None:
        """Log translator plugin registration."""
        self._log.info(
            "outbox_translator_registered",
            context=context_name,
            event_types=sorted(event_types),
            event_count=len(event_types),
        )


class EventSourceProbe(Protocol):
    """Protocol for event source observability.

    Implementations can log, emit metrics, or send traces for event source
    lifecycle and notification handling.
    """

    def event_source_started(self, channel: str) -> None:
        """Called when the event source starts listening."""
        ...

    def event_source_stopped(self) -> None:
        """Called when the event source stops."""
        ...

    def notification_received(self, entry_id: UUID) -> None:
        """Called when a valid notification is received."""
        ...

    def invalid_notification_ignored(self, payload: str, reason: str) -> None:
        """Called when an invalid notification is ignored."""
        ...

    def listener_error(self, error: str) -> None:
        """Called when an error occurs in the listener."""
        ...


class DefaultEventSourceProbe:
    """Default implementation using structlog.

    Logs all event source events with appropriate log levels.
    """

    def __init__(self) -> None:
        """Initialize the probe with a logger."""
        self._log = logger.bind(component="event_source")

    def event_source_started(self, channel: str) -> None:
        """Log event source start."""
        self._log.info("event_source_started", channel=channel)

    def event_source_stopped(self) -> None:
        """Log event source stop."""
        self._log.info("event_source_stopped")

    def notification_received(self, entry_id: UUID) -> None:
        """Log notification received."""
        self._log.debug("notification_received", entry_id=str(entry_id))

    def invalid_notification_ignored(self, payload: str, reason: str) -> None:
        """Log invalid notification ignored."""
        self._log.warning(
            "invalid_notification_ignored",
            payload=payload,
            reason=reason,
        )

    def listener_error(self, error: str) -> None:
        """Log listener error."""
        self._log.error("event_source_listener_error", error=error)
