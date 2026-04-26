"""DataSourceSyncRun entity for tracking sync execution status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# Valid sync run status values representing the lifecycle state machine.
TERMINAL_STATUSES = frozenset({"completed", "failed"})
VALID_STATUSES = frozenset(
    {"pending", "ingesting", "ai_extracting", "applying", "completed", "failed"}
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

    def is_terminal(self) -> bool:
        """Return True if the sync run is in a terminal state.

        Terminal states (completed, failed) cannot be transitioned further.
        The outbox lifecycle handler checks this before applying status updates.
        """
        return self.status in TERMINAL_STATUSES
