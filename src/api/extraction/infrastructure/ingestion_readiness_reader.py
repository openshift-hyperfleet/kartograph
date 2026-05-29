"""SQL reader for ingestion prepare counts without importing Management."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.domain.value_objects import IngestionReadinessSnapshot


class SqlIngestionReadinessReader:
    """Reads prepared data source counts from the shared data_sources table."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def read_for_knowledge_graph(
        self, *, knowledge_graph_id: str
    ) -> IngestionReadinessSnapshot:
        result = await self._session.execute(
            text(
                """
                SELECT
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE last_prepared_commit IS NOT NULL) AS prepared
                FROM data_sources
                WHERE knowledge_graph_id = :knowledge_graph_id
                """
            ),
            {"knowledge_graph_id": knowledge_graph_id},
        )
        row = result.one()
        return IngestionReadinessSnapshot(
            data_source_count=int(row.total or 0),
            prepared_source_count=int(row.prepared or 0),
        )
