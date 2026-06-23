"""SQL reader for ingestion prepare counts without importing Management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from extraction.domain.value_objects import IngestionReadinessSnapshot
from infrastructure.job_packages.readiness import materialized_data_source_counts


class SqlIngestionReadinessReader:
    """Reads prepared data source counts from the shared data_sources table."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        job_package_work_dir_path: Path | None = None,
    ) -> None:
        self._session = session
        self._job_package_work_dir_path = job_package_work_dir_path

    async def read_for_knowledge_graph(
        self, *, knowledge_graph_id: str
    ) -> IngestionReadinessSnapshot:
        total, prepared = await materialized_data_source_counts(
            session=self._session,
            knowledge_graph_id=knowledge_graph_id,
            job_package_work_dir_path=self._job_package_work_dir_path,
        )
        return IngestionReadinessSnapshot(
            data_source_count=total,
            prepared_source_count=prepared,
        )
