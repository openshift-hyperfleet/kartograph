"""Read latest materializable JobPackage identifiers for archive availability checks."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId


class SqlJobPackageArchiveReader:
    """Resolve the latest non-empty JobPackage id emitted for one data source."""

    def __init__(self, *, session: AsyncSession, job_package_work_dir: Path) -> None:
        self._session = session
        self._job_package_work_dir = job_package_work_dir

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
                """
            ),
            {"data_source_id": data_source_id},
        )
        for row in result.fetchall():
            package_id = str(row.job_package_id or "").strip()
            if package_id and self._package_has_repository_content(package_id):
                return package_id
        return None

    def _package_has_repository_content(self, package_id: str) -> bool:
        archive_path = (
            self._job_package_work_dir / JobPackageId(value=package_id).archive_name()
        )
        if not archive_path.is_file():
            return False
        try:
            manifest = JobPackageReader(archive_path).read_manifest()
        except (OSError, ValueError):
            return False
        return manifest.entry_count > 0
