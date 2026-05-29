"""SQL reader for latest prepared JobPackage identifiers without importing Management."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SqlPreparedJobPackageReader:
    """Reads latest prepared JobPackage ids from outbox events for one knowledge graph."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def list_latest_for_knowledge_graph(
        self, *, knowledge_graph_id: str
    ) -> tuple[str, ...]:
        result = await self._session.execute(
            text(
                """
                SELECT DISTINCT ON (payload->>'data_source_id')
                  payload->>'job_package_id' AS job_package_id
                FROM outbox
                WHERE event_type IN ('IngestionPrepared', 'JobPackageProduced')
                  AND payload->>'knowledge_graph_id' = :knowledge_graph_id
                  AND payload->>'job_package_id' IS NOT NULL
                ORDER BY payload->>'data_source_id', occurred_at DESC
                """
            ),
            {"knowledge_graph_id": knowledge_graph_id},
        )
        package_ids = tuple(
            str(row.job_package_id)
            for row in result
            if row.job_package_id is not None and str(row.job_package_id).strip()
        )
        return package_ids
