"""SyncJob aggregate for the Ingestion bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from ulid import ULID


class SyncJobStatus(str, Enum):
    """Valid status transitions for a SyncJob.

    State machine: PENDING -> RUNNING -> COMPLETED | FAILED
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncJob:
    """SyncJob aggregate tracking data source synchronization.

    A SyncJob represents one execution of the ingestion pipeline for a
    given data source. It transitions through PENDING -> RUNNING ->
    COMPLETED or FAILED.

    This aggregate does not emit domain events — sync lifecycle tracking
    is an operational concern managed through direct status updates.
    """

    id: str
    data_source_id: str
    tenant_id: str
    status: SyncJobStatus
    created_at: datetime
    knowledge_graph_id: str | None = field(default=None)
    started_at: datetime | None = field(default=None)
    completed_at: datetime | None = field(default=None)
    error: str | None = field(default=None)

    @classmethod
    def create(
        cls,
        data_source_id: str,
        tenant_id: str,
        knowledge_graph_id: str | None = None,
    ) -> SyncJob:
        """Factory method for creating a new SyncJob in PENDING state.

        Args:
            data_source_id: ID of the data source to sync
            tenant_id: Tenant owning this sync job
            knowledge_graph_id: Optional target knowledge graph ID

        Returns:
            A new SyncJob with status PENDING
        """
        return cls(
            id=str(ULID()),
            data_source_id=data_source_id,
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            status=SyncJobStatus.PENDING,
            created_at=datetime.now(UTC),
        )

    def start(self) -> None:
        """Transition job to RUNNING state."""
        self.status = SyncJobStatus.RUNNING
        self.started_at = datetime.now(UTC)

    def complete(self) -> None:
        """Transition job to COMPLETED state."""
        self.status = SyncJobStatus.COMPLETED
        self.completed_at = datetime.now(UTC)

    def fail(self, error: str) -> None:
        """Transition job to FAILED state with error message.

        Args:
            error: Human-readable error message
        """
        self.status = SyncJobStatus.FAILED
        self.completed_at = datetime.now(UTC)
        self.error = error
