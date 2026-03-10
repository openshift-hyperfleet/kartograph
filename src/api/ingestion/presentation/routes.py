"""FastAPI routes for the Ingestion API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.application.services import SyncJobService
from ingestion.domain.aggregates import SyncJobStatus
from ingestion.domain.exceptions import SyncJobNotFoundError
from ingestion.infrastructure.repositories.sync_job_repository import SyncJobRepository
from ingestion.presentation.models import (
    SyncJobListResponse,
    SyncJobResponse,
    TriggerSyncRequest,
)
from infrastructure.database.dependencies import get_write_session

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_sync_job_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> SyncJobService:
    """Dependency providing a SyncJobService with a PostgreSQL-backed repository.

    Args:
        session: Async write session from FastAPI dependency injection

    Returns:
        SyncJobService instance
    """
    repository = SyncJobRepository(session=session)
    return SyncJobService(repository=repository)


@router.post(
    "/sync-jobs",
    response_model=SyncJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a data source sync",
    description="Create a new SyncJob in PENDING state for the given data source.",
    responses={
        202: {"description": "Sync job accepted and queued"},
        422: {"description": "Validation error — missing or invalid fields"},
    },
)
async def trigger_sync(
    request: TriggerSyncRequest,
    service: Annotated[SyncJobService, Depends(get_sync_job_service)],
) -> SyncJobResponse:
    """Create a new sync job in PENDING state."""
    job = await service.trigger_sync(
        data_source_id=request.data_source_id,
        tenant_id=request.tenant_id,
        knowledge_graph_id=request.knowledge_graph_id,
    )
    return SyncJobResponse.from_domain(job)


@router.get(
    "/sync-jobs",
    response_model=SyncJobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List sync jobs",
    description="List sync jobs with optional filters by status and data source.",
    responses={
        200: {"description": "List of sync jobs"},
    },
)
async def list_sync_jobs(
    service: Annotated[SyncJobService, Depends(get_sync_job_service)],
    status_filter: Annotated[
        SyncJobStatus | None,
        Query(alias="status", description="Filter by job status"),
    ] = None,
    data_source_id: Annotated[
        str | None,
        Query(description="Filter by data source ID"),
    ] = None,
    tenant_id: Annotated[
        str | None,
        Query(description="Filter by tenant ID"),
    ] = None,
) -> SyncJobListResponse:
    """List sync jobs with optional filters."""
    jobs = await service.list_sync_jobs(
        status=status_filter,
        data_source_id=data_source_id,
        tenant_id=tenant_id,
    )
    return SyncJobListResponse(
        sync_jobs=[SyncJobResponse.from_domain(j) for j in jobs],
        total=len(jobs),
    )


@router.get(
    "/sync-jobs/{job_id}",
    response_model=SyncJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a sync job by ID",
    description="Retrieve a single sync job by its unique ID.",
    responses={
        200: {"description": "The sync job"},
        404: {"description": "Sync job not found"},
    },
)
async def get_sync_job(
    job_id: str,
    service: Annotated[SyncJobService, Depends(get_sync_job_service)],
) -> SyncJobResponse:
    """Get a sync job by ID."""
    try:
        job = await service.get_sync_job(job_id)
    except SyncJobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SyncJob {job_id!r} not found",
        )
    return SyncJobResponse.from_domain(job)
