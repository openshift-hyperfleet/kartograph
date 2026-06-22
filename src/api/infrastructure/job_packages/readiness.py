"""JobPackage readiness counts based on on-disk archives."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management.infrastructure.job_package_archive_reader import (
    SqlJobPackageArchiveReader,
)
from shared_kernel.job_package.archive_availability import (
    job_package_archive_exists,
    job_package_work_dir,
)


async def materialized_data_source_counts(
    *,
    session: AsyncSession,
    knowledge_graph_id: str,
    job_package_work_dir_path: Path | None = None,
) -> tuple[int, int]:
    """Return (total_data_sources, data_sources_with_materializable_archives)."""
    work_dir = job_package_work_dir_path or job_package_work_dir()
    result = await session.execute(
        text(
            """
            SELECT id
            FROM data_sources
            WHERE knowledge_graph_id = :knowledge_graph_id
            ORDER BY name
            """
        ),
        {"knowledge_graph_id": knowledge_graph_id},
    )
    data_source_ids = [str(row.id) for row in result.fetchall()]
    archive_reader = SqlJobPackageArchiveReader(
        session=session,
        job_package_work_dir=work_dir,
    )
    prepared_count = 0
    for data_source_id in data_source_ids:
        package_id = await archive_reader.latest_job_package_id_for_data_source(
            data_source_id=data_source_id,
        )
        if job_package_archive_exists(work_dir=work_dir, job_package_id=package_id):
            prepared_count += 1
    return len(data_source_ids), prepared_count
