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
        """Log event translation with operation count."""
        log_level = "debug" if operation_count > 0 else "warning"
        getattr(self._log, log_level)(
            "outbox_event_translated",
            entry_id=str(entry_id),
            event_type=event_type,
            operation_count=operation_count,
        )
