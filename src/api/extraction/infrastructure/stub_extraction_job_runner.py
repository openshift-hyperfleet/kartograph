"""In-memory stub runner for extraction jobs (tests and memory backend)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.domain.prepared_extraction_job_run import PreparedExtractionJobRun
from extraction.ports.extraction_job_runner import IExtractionJobRunner


class StubExtractionJobRunner(IExtractionJobRunner):
    """Simulates successful job completion without launching containers."""

    async def prepare_for_run(
        self,
        job: ExtractionJobRecord,
        *,
        tenant_id: str,
    ) -> PreparedExtractionJobRun:
        _ = tenant_id
        return PreparedExtractionJobRun(
            workdir=Path("/tmp/stub"), prompt=job.description
        )

    async def run_prepared(
        self,
        job: ExtractionJobRecord,
        *,
        prepared: PreparedExtractionJobRun,
    ) -> dict[str, Any]:
        _ = prepared
        return await self.run(job, tenant_id="stub")

    async def run(self, job: ExtractionJobRecord, *, tenant_id: str) -> dict[str, Any]:
        _ = tenant_id
        await asyncio.sleep(0.05)
        target_count = len(job.target_instances) or len(job.target_files) or 1
        return {
            "input_tokens": 100 * target_count,
            "output_tokens": 50 * target_count,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001 * target_count,
            "entities_created": 0,
            "entities_modified": target_count,
            "relationships_created": 0,
        }
