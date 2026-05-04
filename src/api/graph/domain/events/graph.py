"""Graph domain events for the sync lifecycle.

These events are emitted by the Graph context after applying a MutationLog
to the knowledge graph database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MutationsApplied:
    """Emitted when the Graph context successfully applies a MutationLog.

    All graph mutations (node upserts, edge creates, stale node removal)
    have been committed to the Apache AGE database.

    The lifecycle handler transitions the sync run to 'completed' and
    updates the DataSource.last_sync_at timestamp.

    Attributes:
        sync_run_id: The ID of the sync run that completed
        data_source_id: The ID of the data source that was synced
        knowledge_graph_id: The knowledge graph that was updated
        occurred_at: When the mutations were applied
    """

    sync_run_id: str
    data_source_id: str
    knowledge_graph_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class MutationApplicationFailed:
    """Emitted when applying the MutationLog to the graph database fails.

    Failure causes include: DB write conflicts, constraint violations,
    transaction timeouts, etc.

    The lifecycle handler transitions the sync run to 'failed'.

    Attributes:
        sync_run_id: The ID of the sync run that failed
        data_source_id: The ID of the data source that was being synced
        error: Human-readable description of the failure
        occurred_at: When the failure occurred
    """

    sync_run_id: str
    data_source_id: str
    error: str
    occurred_at: datetime
