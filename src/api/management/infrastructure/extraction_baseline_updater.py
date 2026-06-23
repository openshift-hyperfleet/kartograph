"""Update data-source extraction baselines after graph extraction runs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from management.ports.repositories import IDataSourceRepository


def _default_data_source_repository(session: AsyncSession) -> IDataSourceRepository:
    from infrastructure.outbox.repository import OutboxRepository
    from management.infrastructure.repositories.data_source_repository import (
        DataSourceRepository,
    )

    outbox = OutboxRepository(session=session)
    return DataSourceRepository(session=session, outbox=outbox)


async def advance_extraction_baselines_for_knowledge_graph(
    *,
    session: AsyncSession,
    knowledge_graph_id: str,
    data_source_repository: IDataSourceRepository | None = None,
) -> int:
    """Advance extraction baselines to tracked branch head after a successful extraction run."""
    if data_source_repository is None:
        data_source_repository = _default_data_source_repository(session)

    data_sources = await data_source_repository.find_by_knowledge_graph(
        knowledge_graph_id
    )
    updated = 0
    for data_source in data_sources:
        before = data_source.last_extraction_baseline_commit
        data_source.advance_extraction_baseline_to_tracked_head()
        if data_source.last_extraction_baseline_commit == before:
            continue
        await data_source_repository.save(data_source)
        updated += 1
    return updated


async def seed_unset_extraction_baselines_for_knowledge_graph(
    *,
    session: AsyncSession,
    knowledge_graph_id: str,
    data_source_repository: IDataSourceRepository | None = None,
) -> int:
    """Seed NULL extraction baselines from each source's ingested head on a KG."""
    if data_source_repository is None:
        data_source_repository = _default_data_source_repository(session)

    data_sources = await data_source_repository.find_by_knowledge_graph(
        knowledge_graph_id
    )
    updated = 0
    for data_source in data_sources:
        if data_source.last_extraction_baseline_commit is not None:
            continue
        data_source.advance_extraction_baseline_to_ingested_head()
        if data_source.last_extraction_baseline_commit is None:
            continue
        await data_source_repository.save(data_source)
        updated += 1
    return updated
