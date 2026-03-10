"""Repository protocols (ports) for Ingestion bounded context."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ingestion.domain.aggregates import SyncJob, SyncJobStatus


@runtime_checkable
class IIngestionSyncJobRepository(Protocol):
    """Repository for SyncJob aggregate persistence."""

    async def save(self, sync_job: SyncJob) -> None:
        """Persist a sync job (insert or update).

        Args:
            sync_job: The SyncJob aggregate to persist
        """
        ...

    async def get_by_id(self, job_id: str) -> SyncJob | None:
        """Retrieve a sync job by its ID.

        Args:
            job_id: The unique identifier of the sync job

        Returns:
            The SyncJob aggregate, or None if not found
        """
        ...

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
        ...
