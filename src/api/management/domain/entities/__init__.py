"""Management domain entities.

Entities are domain objects with identity but that are not aggregate roots.
They don't emit domain events independently.
"""

from management.domain.entities.data_source_sync_run import DataSourceSyncRun

__all__ = ["DataSourceSyncRun"]
