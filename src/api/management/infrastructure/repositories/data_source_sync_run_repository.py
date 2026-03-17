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
    ) -> None:
        """Initialize repository with database session.

        Args:
            session: AsyncSession from FastAPI dependency injection
        """
        self._session = session

    async def save(self, sync_run: DataSourceSyncRun) -> None:
        """Persist a sync run to PostgreSQL (insert or update).

        Creates a new sync run record or updates an existing one.
        Does not use the outbox pattern since sync runs are entities,
        not aggregate roots.

        Args:
            sync_run: The DataSourceSyncRun entity to persist
        """
        # Upsert sync run in PostgreSQL
        stmt = select(DataSourceSyncRunModel).where(
            DataSourceSyncRunModel.id == sync_run.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            # Update existing — only mutable fields
            model.status = sync_run.status
            model.completed_at = sync_run.completed_at
            model.error = sync_run.error
        else:
            # Create new
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

        # Flush to ensure data is written within the current transaction
        await self._session.flush()

    async def get_by_id(self, sync_run_id: str) -> DataSourceSyncRun | None:
        """Fetch a sync run by its ID from PostgreSQL.

        Args:
            sync_run_id: The unique identifier of the sync run

        Returns:
            The DataSourceSyncRun entity, or None if not found
        """
        stmt = select(DataSourceSyncRunModel).where(
            DataSourceSyncRunModel.id == sync_run_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_by_data_source(self, data_source_id: str) -> list[DataSourceSyncRun]:
        """List all sync runs for a data source.

        Args:
            data_source_id: The data source to list sync runs for

        Returns:
            List of DataSourceSyncRun entities for the data source
        """
        stmt = select(DataSourceSyncRunModel).where(
            DataSourceSyncRunModel.data_source_id == data_source_id
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    def _to_domain(self, model: DataSourceSyncRunModel) -> DataSourceSyncRun:
        """Convert a DataSourceSyncRunModel to a DataSourceSyncRun entity.

        Reconstitutes the entity from database state.

        Args:
            model: The SQLAlchemy model to convert

        Returns:
            A DataSourceSyncRun domain entity
        """
        return DataSourceSyncRun(
            id=model.id,
            data_source_id=model.data_source_id,
            status=model.status,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error=model.error,
            created_at=model.created_at,
        )
