"""SQL reader for latest prepared JobPackage identifiers without importing Management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.application.repository_workspace_paths import repository_folder_for_data_source
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId


class SqlPreparedJobPackageReader:
    """Reads latest materializable JobPackage snapshots from outbox events for one KG."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        job_package_work_dir: Path,
    ) -> None:
        self._session = session
        self._job_package_work_dir = job_package_work_dir

    async def list_latest_for_knowledge_graph(
        self, *, knowledge_graph_id: str
    ) -> tuple[PreparedJobPackageSource, ...]:
        result = await self._session.execute(
            text(
                """
                SELECT
                  payload->>'data_source_id' AS data_source_id,
                  payload->>'job_package_id' AS job_package_id,
                  ds.name AS data_source_name,
                  occurred_at
                FROM outbox o
                LEFT JOIN data_sources ds ON ds.id = payload->>'data_source_id'
                WHERE o.event_type IN ('IngestionPrepared', 'JobPackageProduced')
                  AND payload->>'knowledge_graph_id' = :knowledge_graph_id
                  AND payload->>'job_package_id' IS NOT NULL
                ORDER BY payload->>'data_source_id', o.occurred_at DESC
                """
            ),
            {"knowledge_graph_id": knowledge_graph_id},
        )
        rows = result.fetchall()

        by_source: dict[str, list] = {}
        for row in rows:
            data_source_id = str(row.data_source_id or "").strip()
            if not data_source_id:
                continue
            by_source.setdefault(data_source_id, []).append(row)

        selected: list[PreparedJobPackageSource] = []
        for data_source_id in sorted(by_source):
            source = self._first_materializable_source(
                data_source_id=data_source_id,
                rows=by_source[data_source_id],
            )
            if source is not None:
                selected.append(source)

        return tuple(selected)

    def _first_materializable_source(
        self, *, data_source_id: str, rows
    ) -> PreparedJobPackageSource | None:
        for row in rows:
            package_id = str(row.job_package_id or "").strip()
            if not package_id:
                continue
            if not self._package_has_repository_content(package_id):
                continue
            data_source_name = str(row.data_source_name or "").strip() or data_source_id
            return PreparedJobPackageSource(
                package_id=package_id,
                data_source_id=data_source_id,
                data_source_name=data_source_name,
                repository_folder=repository_folder_for_data_source(
                    name=data_source_name,
                    data_source_id=data_source_id,
                ),
            )
        return None

    def _package_has_repository_content(self, package_id: str) -> bool:
        archive_path = self._job_package_work_dir / JobPackageId(
            value=package_id
        ).archive_name()
        if not archive_path.is_file():
            return False
        try:
            manifest = JobPackageReader(archive_path).read_manifest()
        except (OSError, ValueError):
            return False
        return manifest.entry_count > 0
