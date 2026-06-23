"""Port for executing one materialized extraction job."""

from __future__ import annotations

from typing import Any, Protocol

from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.domain.prepared_extraction_job_run import PreparedExtractionJobRun


class IExtractionJobRunner(Protocol):
    """Runs one extraction job and returns completion metrics."""

    async def prepare_for_run(
        self,
        job: ExtractionJobRecord,
        *,
        tenant_id: str,
    ) -> PreparedExtractionJobRun:
        """Materialize workspace artifacts (short-lived DB usage)."""
        ...

    async def run_prepared(
        self,
        job: ExtractionJobRecord,
        *,
        prepared: PreparedExtractionJobRun,
    ) -> dict[str, Any]:
        """Execute a prepared job without an open ORM session."""
        ...

    async def run(self, job: ExtractionJobRecord, *, tenant_id: str) -> dict[str, Any]:
        """Execute the job and return token/cost/write metrics."""
        ...
