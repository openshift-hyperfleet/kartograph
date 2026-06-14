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
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.extraction_workload.graph_mutation_writer import GraphWorkloadGraphMutationWriter
from infrastructure.extraction_workload.graph_reader import GraphWorkloadGraphReader
from infrastructure.extraction_workload.schema_service import GraphWorkloadSchemaService
from infrastructure.extraction_workload.target_context_enricher import (
    GraphExtractionJobTargetContextEnricher,
)
from infrastructure.settings import get_database_settings
from sqlalchemy.ext.asyncio import AsyncSession


def create_extraction_job_runner(
    *,
    session: AsyncSession | None = None,
    settings: ExtractionWorkloadRuntimeSettings | None = None,
    pool: ConnectionPool | None = None,
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

    resolved_pool = pool or get_age_connection_pool()
    db_settings = get_database_settings()
    graph_reader = GraphWorkloadGraphReader(pool=resolved_pool, settings=db_settings)
    schema_service = GraphWorkloadSchemaService(
        session=session,
        mutation_writer=GraphWorkloadGraphMutationWriter(
            pool=resolved_pool,
            settings=db_settings,
            session=session,
        ),
        graph_reader=graph_reader,
    )
    materializer = ExtractionJobWorkdirMaterializer(
        settings=resolved,
        prepared_job_package_reader=prepared_reader,
        archive_hydrator=JobPackageArchiveHydrator(
            session=session,
            job_package_work_dir=Path(resolved.job_package_work_dir),
        ),
        target_context_enricher=GraphExtractionJobTargetContextEnricher(
            graph_reader=graph_reader,
            schema_service=schema_service,
        ),
    )
    return AgenticCiExtractionJobRunner(
        settings=resolved,
        workdir_materializer=materializer,
    )
