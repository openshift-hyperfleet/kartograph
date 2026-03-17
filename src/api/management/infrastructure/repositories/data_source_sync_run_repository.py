"""PostgreSQL implementation of IDataSourceSyncRunRepository.

This repository manages DataSourceSyncRun persistence in PostgreSQL.
Sync runs are entities (not aggregate roots) and do not emit domain
events through the outbox pattern.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from management.domain.entities import DataSourceSyncRun
from management.infrastructure.models import DataSourceSyncRunModel
from management.infrastructure.observability import (
    DefaultSyncRunRepositoryProbe,
    SyncRunRepositoryProbe,
)
from management.ports.repositories import IDataSourceSyncRunRepository


class DataSourceSyncRunRepository(IDataSourceSyncRunRepository):
    """Repository managing PostgreSQL storage for DataSourceSyncRun entities.

    This implementation stores sync run records in PostgreSQL. Sync runs
    are simple entities that track synchronization execution status.

    Unlike aggregate repositories, this does not use the transactional
    outbox pattern since sync runs do not emit domain events.
    """

    def __init__(
        self,
        session: AsyncSession,
        probe: SyncRunRepositoryProbe | None = None,
    ) -> None:
        self._session = session
        self._probe = probe or DefaultSyncRunRepositoryProbe()

    async def save(self, sync_run: DataSourceSyncRun) -> None:
        """Persist a sync run to PostgreSQL (insert or update)."""
        stmt = select(DataSourceSyncRunModel).where(
            DataSourceSyncRunModel.id == sync_run.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.status = sync_run.status
            model.completed_at = sync_run.completed_at
            model.error = sync_run.error
        else:
            model = DataSourceSyncRunModel(
                id=sync_run.id,
                data_source_id=sync_run.data_source_id,
                status=sync_run.status,
                started_at=sync_run.started_at,
                completed_at=sync_run.completed_at,
                error=sync_run.error,
                created_at=sync_run.created_at,
            )
            self._session.add(model)

        await self._session.flush()

        self._probe.sync_run_saved(sync_run.id, sync_run.data_source_id)

    async def get_by_id(self, sync_run_id: str) -> DataSourceSyncRun | None:
        stmt = select(DataSourceSyncRunModel).where(
            DataSourceSyncRunModel.id == sync_run_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.sync_run_not_found(sync_run_id)
            return None

        self._probe.sync_run_retrieved(sync_run_id)
        return self._to_domain(model)

    async def find_by_data_source(self, data_source_id: str) -> list[DataSourceSyncRun]:
        stmt = select(DataSourceSyncRunModel).where(
            DataSourceSyncRunModel.data_source_id == data_source_id
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        runs = [self._to_domain(model) for model in models]
        self._probe.sync_runs_listed(data_source_id, len(runs))
        return runs

    def _to_domain(self, model: DataSourceSyncRunModel) -> DataSourceSyncRun:
        """Reconstitute entity from database state."""
        return DataSourceSyncRun(
            id=model.id,
            data_source_id=model.data_source_id,
            status=model.status,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error=model.error,
            created_at=model.created_at,
        )
