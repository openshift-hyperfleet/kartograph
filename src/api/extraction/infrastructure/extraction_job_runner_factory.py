"""Factory helpers for extraction job runners."""

from __future__ import annotations

from pathlib import Path

from extraction.infrastructure.agentic_ci_extraction_job_runner import AgenticCiExtractionJobRunner
from extraction.infrastructure.extraction_job_workdir_materializer import (
    ExtractionJobWorkdirMaterializer,
)
from extraction.infrastructure.prepared_job_package_reader import SqlPreparedJobPackageReader
from extraction.infrastructure.stub_extraction_job_runner import StubExtractionJobRunner
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
from extraction.ports.extraction_job_runner import IExtractionJobRunner
from sqlalchemy.ext.asyncio import AsyncSession


def create_extraction_job_runner(
    *,
    session: AsyncSession | None = None,
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> IExtractionJobRunner:
    """Build the configured extraction job runner implementation."""
    resolved = settings or get_extraction_workload_runtime_settings()
    if resolved.job_runner == "stub":
        return StubExtractionJobRunner()
    if session is None:
        raise ValueError("database session is required for agentic-ci extraction jobs")
    prepared_reader = SqlPreparedJobPackageReader(
        session=session,
        job_package_work_dir=Path(resolved.job_package_work_dir),
    )
    from infrastructure.job_packages.archive_hydrator import JobPackageArchiveHydrator

    materializer = ExtractionJobWorkdirMaterializer(
        settings=resolved,
        prepared_job_package_reader=prepared_reader,
        archive_hydrator=JobPackageArchiveHydrator(
            session=session,
            job_package_work_dir=Path(resolved.job_package_work_dir),
        ),
    )
    return AgenticCiExtractionJobRunner(
        settings=resolved,
        workdir_materializer=materializer,
    )
