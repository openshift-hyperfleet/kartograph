"""DataSourceSyncRun entity for tracking sync execution status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DataSourceSyncRun:
    """Entity tracking the execution of a data source sync.

    This is a subordinate entity of DataSource. It does not emit domain
    events independently — sync lifecycle tracking is an operational
    concern, not a domain event.

    Valid status values: "pending", "running", "completed", "failed"
    """

    id: str
    data_source_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    error: str | None
    created_at: datetime
