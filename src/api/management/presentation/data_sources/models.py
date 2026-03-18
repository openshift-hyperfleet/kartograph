"""Request and response models for Data Source API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from management.domain.aggregates import DataSource
from management.domain.entities import DataSourceSyncRun


class CreateDataSourceRequest(BaseModel):
    """Request to create a data source.

    Attributes:
        name: Data source name (1-100 characters)
        adapter_type: Adapter type string (validated against DataSourceAdapterType in route)
        connection_config: Key-value connection configuration
        credentials: Optional write-only credentials (never returned in responses)
    """

    name: str = Field(min_length=1, max_length=100)
    adapter_type: str
    connection_config: dict[str, str]
    credentials: dict[str, str] | None = None


class UpdateDataSourceRequest(BaseModel):
    """Request to partially update a data source.

    Attributes:
        name: Optional new name (1-100 characters)
        connection_config: Optional new connection configuration
        credentials: Optional new credentials (write-only)
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    connection_config: dict[str, str] | None = None
    credentials: dict[str, str] | None = None


class DataSourceResponse(BaseModel):
    """Response containing data source details.

    Credentials are never returned. Instead, has_credentials indicates
    whether credentials have been configured.

    Attributes:
        id: Data source ID (ULID)
        knowledge_graph_id: Parent knowledge graph ID
        tenant_id: Tenant ID this data source belongs to
        name: Data source name
        adapter_type: Adapter type string
        connection_config: Connection configuration key-value pairs
        has_credentials: Whether credentials are configured
        schedule_type: Schedule type (manual, cron, interval)
        schedule_value: Schedule expression (None for manual)
        last_sync_at: Last successful sync timestamp
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id: str
    knowledge_graph_id: str
    tenant_id: str
    name: str
    adapter_type: str
    connection_config: dict[str, str]
    has_credentials: bool
    schedule_type: str
    schedule_value: str | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, ds: DataSource) -> DataSourceResponse:
        """Convert domain DataSource aggregate to API response.

        Args:
            ds: DataSource domain aggregate

        Returns:
            DataSourceResponse with data source details
        """
        return cls(
            id=ds.id.value,
            knowledge_graph_id=ds.knowledge_graph_id,
            tenant_id=ds.tenant_id,
            name=ds.name,
            adapter_type=ds.adapter_type.value,
            connection_config=ds.connection_config,
            has_credentials=ds.credentials_path is not None,
            schedule_type=ds.schedule.schedule_type.value,
            schedule_value=ds.schedule.value,
            last_sync_at=ds.last_sync_at,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
        )


class DataSourceListResponse(BaseModel):
    """Response containing a paginated list of data sources.

    Attributes:
        items: List of data source details
        total: Total number of data sources (before pagination)
        offset: Number of items skipped
        limit: Maximum number of items returned
    """

    items: list[DataSourceResponse]
    total: int
    offset: int
    limit: int


class SyncRunResponse(BaseModel):
    """Response containing sync run details.

    Attributes:
        id: Sync run ID
        data_source_id: Data source this sync belongs to
        status: Sync run status (pending, running, completed, failed)
        started_at: Sync start timestamp
        completed_at: Sync completion timestamp (None if not complete)
        created_at: Record creation timestamp
    """

    id: str
    data_source_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    error: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, sync_run: DataSourceSyncRun) -> SyncRunResponse:
        """Convert domain DataSourceSyncRun entity to API response.

        Args:
            sync_run: DataSourceSyncRun domain entity

        Returns:
            SyncRunResponse with sync run details
        """
        return cls(
            id=sync_run.id,
            data_source_id=sync_run.data_source_id,
            status=sync_run.status,
            started_at=sync_run.started_at,
            completed_at=sync_run.completed_at,
            error=sync_run.error,
            created_at=sync_run.created_at,
        )
