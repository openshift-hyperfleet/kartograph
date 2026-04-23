"""Pydantic models for Data Source requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from management.domain.aggregates import DataSource
from management.domain.entities import DataSourceSyncRun


class CreateDataSourceRequest(BaseModel):
    """Request model for creating a data source."""

    name: str = Field(
        ...,
        description="Name of the data source",
        min_length=1,
        max_length=100,
    )
    adapter_type: str = Field(
        ...,
        description="Adapter type (e.g., 'github')",
    )
    connection_config: dict = Field(
        ...,
        description="Connection configuration key-value pairs for the adapter",
    )
    credentials: dict | None = Field(
        default=None,
        description="Optional credentials to encrypt and store securely",
    )


class DataSourceResponse(BaseModel):
    """Response model for a data source."""

    id: str = Field(..., description="Data Source ID (ULID format)")
    knowledge_graph_id: str = Field(
        ..., description="Knowledge Graph ID this DS belongs to"
    )
    tenant_id: str = Field(..., description="Tenant ID this DS belongs to")
    name: str = Field(..., description="Data source name")
    adapter_type: str = Field(..., description="Adapter type (e.g., 'github')")
    schedule_type: str = Field(
        ..., description="Schedule type (e.g., 'manual', 'cron')"
    )
    last_sync_at: datetime | None = Field(
        None, description="When the last sync completed"
    )
    created_at: datetime = Field(..., description="When the DS was created")
    updated_at: datetime = Field(..., description="When the DS was last updated")

    @classmethod
    def from_domain(cls, ds: DataSource) -> DataSourceResponse:
        """Convert domain DataSource aggregate to API response.

        Args:
            ds: DataSource domain aggregate

        Returns:
            DataSourceResponse with DS details
        """
        return cls(
            id=ds.id.value,
            knowledge_graph_id=ds.knowledge_graph_id,
            tenant_id=ds.tenant_id,
            name=ds.name,
            adapter_type=ds.adapter_type.value,
            schedule_type=ds.schedule.schedule_type.value,
            last_sync_at=ds.last_sync_at,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
        )


class SyncRunResponse(BaseModel):
    """Response model for a data source sync run."""

    id: str = Field(..., description="Sync Run ID (ULID format)")
    data_source_id: str = Field(..., description="Data Source ID this run belongs to")
    status: str = Field(
        ..., description="Sync run status (pending, running, completed, failed)"
    )
    started_at: datetime = Field(..., description="When the sync run started")
    completed_at: datetime | None = Field(
        None, description="When the sync run completed"
    )
    error: str | None = Field(None, description="Error message if the sync run failed")
    created_at: datetime = Field(
        ..., description="When the sync run record was created"
    )

    @classmethod
    def from_domain(cls, run: DataSourceSyncRun) -> SyncRunResponse:
        """Convert domain DataSourceSyncRun entity to API response.

        Args:
            run: DataSourceSyncRun domain entity

        Returns:
            SyncRunResponse with sync run details
        """
        return cls(
            id=run.id,
            data_source_id=run.data_source_id,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error=run.error,
            created_at=run.created_at,
        )
