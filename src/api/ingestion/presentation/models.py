"""Pydantic request/response models for the Ingestion API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ingestion.domain.aggregates import SyncJob, SyncJobStatus


class TriggerSyncRequest(BaseModel):
    """Request body for POST /ingestion/sync-jobs."""

    data_source_id: str = Field(..., description="ID of the data source to sync")
    tenant_id: str = Field(..., description="Tenant owning this sync job")
    knowledge_graph_id: str | None = Field(
        None, description="Optional target knowledge graph ID"
    )


class SyncJobResponse(BaseModel):
    """Response model for a single SyncJob."""

    id: str
    data_source_id: str
    tenant_id: str
    knowledge_graph_id: str | None
    status: SyncJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, job: SyncJob) -> SyncJobResponse:
        """Convert a SyncJob domain aggregate to a response model.

        Args:
            job: The SyncJob domain aggregate

        Returns:
            A SyncJobResponse suitable for API serialization
        """
        return cls(
            id=job.id,
            data_source_id=job.data_source_id,
            tenant_id=job.tenant_id,
            knowledge_graph_id=job.knowledge_graph_id,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error=job.error,
            created_at=job.created_at,
        )


class SyncJobListResponse(BaseModel):
    """Response model for listing SyncJobs."""

    sync_jobs: list[SyncJobResponse]
    total: int
