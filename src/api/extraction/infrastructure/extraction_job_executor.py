"""Execute one materialized extraction job."""

from __future__ import annotations

from typing import Any

from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.infrastructure.extraction_job_runner_factory import create_extraction_job_runner
from extraction.infrastructure.stub_extraction_job_runner import StubExtractionJobRunner
from extraction.infrastructure.workload_runtime_settings import get_extraction_workload_runtime_settings
from extraction.ports.extraction_job_runner import IExtractionJobRunner
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class ExtractionJobExecutor:
    """Runs one extraction job using the configured runner backend."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        runner: IExtractionJobRunner | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._runner = runner

    async def execute(self, job: ExtractionJobRecord, *, tenant_id: str) -> dict[str, Any]:
        if self._runner is not None:
            return await self._runner.run(job, tenant_id=tenant_id)
        settings = get_extraction_workload_runtime_settings()
        if settings.job_runner == "stub" or self._session_factory is None:
            return await StubExtractionJobRunner().run(job, tenant_id=tenant_id)
        async with self._session_factory() as session:
            runner = create_extraction_job_runner(session=session, settings=settings)
            return await runner.run(job, tenant_id=tenant_id)
