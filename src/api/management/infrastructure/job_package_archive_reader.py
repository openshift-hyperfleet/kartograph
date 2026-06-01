"""Read latest JobPackage identifiers for data source archive availability checks."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SqlJobPackageArchiveReader:
    """Resolve the latest JobPackage id emitted for one data source."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def latest_job_package_id_for_data_source(
        self, *, data_source_id: str
    ) -> str | None:
        result = await self._session.execute(
            text(
                """
                SELECT payload->>'job_package_id' AS job_package_id
                FROM outbox
                WHERE event_type IN ('IngestionPrepared', 'JobPackageProduced')
                  AND payload->>'data_source_id' = :data_source_id
                  AND payload->>'job_package_id' IS NOT NULL
                ORDER BY occurred_at DESC
                LIMIT 1
                """
            ),
            {"data_source_id": data_source_id},
        )
        row = result.one_or_none()
        if row is None or row.job_package_id is None:
            return None
        package_id = str(row.job_package_id).strip()
        return package_id or None
