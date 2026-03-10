"""Application services for the Ingestion bounded context."""

from __future__ import annotations

from ingestion.domain.aggregates import SyncJob, SyncJobStatus
from ingestion.domain.exceptions import SyncJobNotFoundError
from ingestion.ports.repositories import IIngestionSyncJobRepository


class SyncJobService:
    """Application service coordinating SyncJob operations.

    Orchestrates the creation and retrieval of SyncJob aggregates
    using the injected repository port.
    """

    def __init__(self, repository: IIngestionSyncJobRepository) -> None:
        """Initialize with a sync job repository.

        Args:
            repository: Repository implementing IIngestionSyncJobRepository
        """
        self._repository = repository

    async def trigger_sync(
        self,
        data_source_id: str,
        tenant_id: str,
        knowledge_graph_id: str | None = None,
    ) -> SyncJob:
        """Create a new SyncJob in PENDING state and persist it.

        Args:
            data_source_id: ID of the data source to sync
            tenant_id: Tenant owning this sync job
            knowledge_graph_id: Optional target knowledge graph ID

        Returns:
            The created SyncJob aggregate
        """
        job = SyncJob.create(
            data_source_id=data_source_id,
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        await self._repository.save(job)
        return job

    async def get_sync_job(self, job_id: str) -> SyncJob:
        """Retrieve a sync job by ID.

        Args:
            job_id: The unique identifier of the sync job

        Returns:
            The SyncJob aggregate

        Raises:
            SyncJobNotFoundError: If no job exists with the given ID
        """
        job = await self._repository.get_by_id(job_id)
        if job is None:
            raise SyncJobNotFoundError(f"SyncJob {job_id!r} not found")
        return job

    async def list_sync_jobs(
        self,
        *,
        status: SyncJobStatus | None = None,
        data_source_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[SyncJob]:
        """List sync jobs with optional filters.

        Args:
            status: Filter by status (optional)
            data_source_id: Filter by data source ID (optional)
            tenant_id: Filter by tenant ID (optional)

        Returns:
            List of matching SyncJob aggregates
        """
        return await self._repository.list_sync_jobs(
            status=status,
            data_source_id=data_source_id,
            tenant_id=tenant_id,
        )
