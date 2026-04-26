"""Extraction domain events for the sync lifecycle.

These events are emitted by the Extraction context after processing
a JobPackage via AI-based entity extraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MutationLogProduced:
    """Emitted when the Extraction context successfully produces a MutationLog.

    A MutationLog is a JSONL file describing graph operations (node upserts,
    edge creates, deletions by staleness) that the Graph context must apply.

    The lifecycle handler transitions the sync run to 'applying'.

    Attributes:
        sync_run_id: The ID of the sync run that produced this log
        data_source_id: The ID of the data source that was extracted
        knowledge_graph_id: The knowledge graph being populated
        mutation_log_id: Identifier for the produced MutationLog
        occurred_at: When the mutation log was produced
    """

    sync_run_id: str
    data_source_id: str
    knowledge_graph_id: str
    mutation_log_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class ExtractionFailed:
    """Emitted when AI-based entity extraction fails.

    Failure causes include: Claude API errors, token limits exceeded,
    malformed JobPackage content, etc.

    The lifecycle handler transitions the sync run to 'failed'.

    Attributes:
        sync_run_id: The ID of the sync run that failed
        data_source_id: The ID of the data source that was being extracted
        error: Human-readable description of the failure
        occurred_at: When the failure occurred
    """

    sync_run_id: str
    data_source_id: str
    error: str
    occurred_at: datetime
