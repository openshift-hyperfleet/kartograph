"""PostgreSQL implementation of IDataSourceRepository.

This repository manages DataSource persistence in PostgreSQL and
uses the transactional outbox pattern for domain event publishing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from management.infrastructure.models import DataSourceModel
from management.infrastructure.observability import (
    DataSourceRepositoryProbe,
    DefaultDataSourceRepositoryProbe,
)
from management.infrastructure.outbox import ManagementEventSerializer
from management.ports.exceptions import DuplicateDataSourceNameError
from management.ports.repositories import IDataSourceRepository
from shared_kernel.datasource_types import DataSourceAdapterType

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class DataSourceRepository(IDataSourceRepository):
    """Repository managing PostgreSQL storage for DataSource aggregates.

    Write operations use the transactional outbox pattern:
    - Domain events are collected from the aggregate
    - Events are appended to the outbox table (same transaction as PostgreSQL)
    - The outbox worker processes events asynchronously
    """

    def __init__(
        self,
        session: AsyncSession,
        outbox: "OutboxRepository",
        probe: DataSourceRepositoryProbe | None = None,
        serializer: ManagementEventSerializer | None = None,
    ) -> None:
        self._session = session
        self._outbox = outbox
        self._probe = probe or DefaultDataSourceRepositoryProbe()
        self._serializer = serializer or ManagementEventSerializer()

    async def save(self, data_source: DataSource) -> None:
        """Persist data source metadata to PostgreSQL, events to outbox.

        Raises:
            DuplicateDataSourceNameError: If name already exists in the KG
        """
        try:
            stmt = select(DataSourceModel).where(
                DataSourceModel.id == data_source.id.value
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()

            if model:
                model.name = data_source.name
                model.connection_config = data_source.connection_config
                model.credentials_path = data_source.credentials_path
                model.schedule_type = data_source.schedule.schedule_type.value
                model.schedule_value = data_source.schedule.value
                model.last_sync_at = data_source.last_sync_at
                model.updated_at = data_source.updated_at
            else:
                model = DataSourceModel(
                    id=data_source.id.value,
                    knowledge_graph_id=data_source.knowledge_graph_id,
                    tenant_id=data_source.tenant_id,
                    name=data_source.name,
                    adapter_type=data_source.adapter_type.value,
                    connection_config=data_source.connection_config,
                    credentials_path=data_source.credentials_path,
                    schedule_type=data_source.schedule.schedule_type.value,
                    schedule_value=data_source.schedule.value,
                    last_sync_at=data_source.last_sync_at,
                    created_at=data_source.created_at,
                    updated_at=data_source.updated_at,
                )
                self._session.add(model)

            await self._session.flush()

            events = data_source.collect_events()
            for event in events:
                payload = self._serializer.serialize(event)
                await self._outbox.append(
                    event_type=type(event).__name__,
                    payload=payload,
                    occurred_at=event.occurred_at,
                    aggregate_type="data_source",
                    aggregate_id=data_source.id.value,
                )

            self._probe.data_source_saved(
                data_source.id.value, data_source.knowledge_graph_id
            )

        except IntegrityError as e:
            if "uq_data_sources_kg_name" in str(e):
                self._probe.duplicate_data_source_name(
                    data_source.name, data_source.knowledge_graph_id
                )
                raise DuplicateDataSourceNameError(
                    f"Data source '{data_source.name}' already exists "
                    f"in knowledge graph '{data_source.knowledge_graph_id}'"
                ) from e
            raise

    async def get_by_id(self, data_source_id: DataSourceId) -> DataSource | None:
        stmt = select(DataSourceModel).where(DataSourceModel.id == data_source_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.data_source_not_found(data_source_id.value)
            return None

        self._probe.data_source_retrieved(data_source_id.value)
        return self._to_domain(model)

    async def find_by_knowledge_graph(
        self, knowledge_graph_id: str, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[DataSource], int]:
        # Count query
        count_stmt = (
            select(func.count())
            .select_from(DataSourceModel)
            .where(DataSourceModel.knowledge_graph_id == knowledge_graph_id)
        )
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        # Paginated query
        stmt = (
            select(DataSourceModel)
            .where(DataSourceModel.knowledge_graph_id == knowledge_graph_id)
            .offset(offset)
            .limit(limit)
            .order_by(DataSourceModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        data_sources = [self._to_domain(model) for model in models]
        self._probe.data_sources_listed(knowledge_graph_id, len(data_sources))
        return data_sources, total

    async def delete(self, data_source: DataSource) -> bool:
        stmt = select(DataSourceModel).where(DataSourceModel.id == data_source.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        events = data_source.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="data_source",
                aggregate_id=data_source.id.value,
            )

        await self._session.delete(model)
        await self._session.flush()

        self._probe.data_source_deleted(data_source.id.value)
        return True

    def _to_domain(self, model: DataSourceModel) -> DataSource:
        """Reconstitute aggregate from database state without generating events."""
        return DataSource(
            id=DataSourceId(value=model.id),
            knowledge_graph_id=model.knowledge_graph_id,
            tenant_id=model.tenant_id,
            name=model.name,
            adapter_type=DataSourceAdapterType(model.adapter_type),
            connection_config=dict(model.connection_config),
            credentials_path=model.credentials_path,
            schedule=Schedule(
                schedule_type=ScheduleType(model.schedule_type),
                value=model.schedule_value,
            ),
            last_sync_at=model.last_sync_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
