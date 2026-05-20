"""DataSourceSyncRun entity for tracking sync execution status."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Valid sync run status values representing the lifecycle state machine.
TERMINAL_STATUSES = frozenset({"completed", "failed"})
VALID_STATUSES = frozenset(
    {"pending", "ingesting", "ai_extracting", "applying", "completed", "failed"}
)


@dataclass
class MutationLogRunMetadata:
    """Run-level metadata captured for a produced/applied mutation log."""

    mutation_log_id: str
    knowledge_graph_id: str
    session_id: str | None
    actor_id: str | None
    started_at: datetime
    completed_at: datetime | None = None
    token_usage_total: int | None = None
    cost_total_usd: float | None = None
    operation_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_log_id": self.mutation_log_id,
            "knowledge_graph_id": self.knowledge_graph_id,
            "session_id": self.session_id,
            "actor_id": self.actor_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at is not None else None
            ),
            "token_usage_total": self.token_usage_total,
            "cost_total_usd": self.cost_total_usd,
            "operation_counts": self.operation_counts,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MutationLogRunMetadata":
        return cls(
            mutation_log_id=str(raw["mutation_log_id"]),
            knowledge_graph_id=str(raw["knowledge_graph_id"]),
            session_id=raw.get("session_id"),
            actor_id=raw.get("actor_id"),
            started_at=datetime.fromisoformat(str(raw["started_at"])),
            completed_at=(
                datetime.fromisoformat(str(raw["completed_at"]))
                if raw.get("completed_at")
                else None
            ),
            token_usage_total=(
                int(raw["token_usage_total"])
                if raw.get("token_usage_total") is not None
                else None
            ),
            cost_total_usd=(
                float(raw["cost_total_usd"])
                if raw.get("cost_total_usd") is not None
                else None
            ),
            operation_counts={
                str(k): int(v) for k, v in (raw.get("operation_counts") or {}).items()
            },
        )


@dataclass
class DataSourceSyncRun:
    """Entity tracking the execution of a data source sync.

    This is a subordinate entity of DataSource. Sync lifecycle tracking
    is driven by domain events flowing through the outbox:

    Lifecycle state machine:
      pending        (initial state, sync run created)
      → ingesting    (SyncStarted event processed, ingestion pipeline running)
      → ai_extracting (JobPackageProduced, AI entity extraction triggered)
      → applying     (MutationLogProduced, graph mutations being applied)
      → completed    (MutationsApplied, sync finished successfully)
      → failed       (IngestionFailed / ExtractionFailed / MutationApplicationFailed)

    Terminal states: completed, failed — no further transitions allowed.

    Valid status values: "pending", "ingesting", "ai_extracting",
                         "applying", "completed", "failed"
    """

    id: str
    data_source_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    error: str | None
    created_at: datetime
    logs: list[str] = field(default_factory=list)
    mutation_log_run: MutationLogRunMetadata | None = None

    def is_terminal(self) -> bool:
        """Return True if the sync run is in a terminal state.

        Terminal states (completed, failed) cannot be transitioned further.
        The outbox lifecycle handler checks this before applying status updates.
        """
        return self.status in TERMINAL_STATUSES
