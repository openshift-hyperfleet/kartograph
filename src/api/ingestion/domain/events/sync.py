"""Ingestion domain events for the sync lifecycle.

These events are emitted by the Ingestion context during data extraction
and packaging. They feed into the sync lifecycle state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class JobPackageProduced:
    """Emitted when the ingestion pipeline successfully produces a JobPackage.

    This event signals that raw data has been extracted from the data source
    and packaged into a ZIP archive ready for AI-based entity extraction.

    The Extraction context consumes this event to begin processing.
    The lifecycle handler transitions the sync run to 'ai_extracting'.

    Attributes:
        sync_run_id: The ID of the sync run that produced this package
        data_source_id: The ID of the data source that was ingested
        knowledge_graph_id: The knowledge graph this package feeds
        job_package_id: The ULID identifier of the produced JobPackage
        occurred_at: When the package was produced
    """

    sync_run_id: str
    data_source_id: str
    knowledge_graph_id: str
    job_package_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class IngestionFailed:
    """Emitted when the ingestion pipeline fails.

    Failure causes include: expired credentials, unreachable source,
    adapter errors, packaging failures, etc.

    The lifecycle handler transitions the sync run to 'failed'.

    Attributes:
        sync_run_id: The ID of the sync run that failed
        data_source_id: The ID of the data source that was being ingested
        error: Human-readable description of the failure
        occurred_at: When the failure occurred
    """

    sync_run_id: str
    data_source_id: str
    error: str
    occurred_at: datetime
