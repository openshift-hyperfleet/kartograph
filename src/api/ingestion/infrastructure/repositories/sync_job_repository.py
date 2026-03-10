"""PostgreSQL implementation of IIngestionSyncJobRepository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.domain.aggregates import SyncJob, SyncJobStatus
from ingestion.infrastructure.models import SyncJobModel
from ingestion.ports.repositories import IIngestionSyncJobRepository


class SyncJobRepository(IIngestionSyncJobRepository):
    """Repository managing PostgreSQL storage for SyncJob aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: AsyncSession from FastAPI dependency injection
        """
        self._session = session

    async def save(self, sync_job: SyncJob) -> None:
        """Persist a sync job (insert or update).

        Args:
            sync_job: The SyncJob aggregate to persist
        """
        stmt = select(SyncJobModel).where(SyncJobModel.id == sync_job.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.status = sync_job.status.value
            model.started_at = sync_job.started_at
            model.completed_at = sync_job.completed_at
            model.error = sync_job.error
        else:
            model = SyncJobModel(
                id=sync_job.id,
                data_source_id=sync_job.data_source_id,
                tenant_id=sync_job.tenant_id,
                knowledge_graph_id=sync_job.knowledge_graph_id,
                status=sync_job.status.value,
                started_at=sync_job.started_at,
                completed_at=sync_job.completed_at,
                error=sync_job.error,
                created_at=sync_job.created_at,
            )
            self._session.add(model)

        await self._session.flush()
        await self._session.commit()

    async def get_by_id(self, job_id: str) -> SyncJob | None:
        """Retrieve a sync job by its ID.

        Args:
            job_id: The unique identifier of the sync job

        Returns:
            The SyncJob aggregate, or None if not found
        """
        stmt = select(SyncJobModel).where(SyncJobModel.id == job_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

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
        stmt = select(SyncJobModel)

        if status is not None:
            stmt = stmt.where(SyncJobModel.status == status.value)
        if data_source_id is not None:
            stmt = stmt.where(SyncJobModel.data_source_id == data_source_id)
        if tenant_id is not None:
            stmt = stmt.where(SyncJobModel.tenant_id == tenant_id)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    def _to_domain(self, model: SyncJobModel) -> SyncJob:
        """Convert a SyncJobModel to a SyncJob domain aggregate.

        Args:
            model: The SQLAlchemy model to convert

        Returns:
            A SyncJob domain aggregate
        """
        return SyncJob(
            id=model.id,
            data_source_id=model.data_source_id,
            tenant_id=model.tenant_id,
            knowledge_graph_id=model.knowledge_graph_id,
            status=SyncJobStatus(model.status),
            started_at=model.started_at,
            completed_at=model.completed_at,
            error=model.error,
            created_at=model.created_at,
        )
