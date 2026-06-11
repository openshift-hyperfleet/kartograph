"""Port for executing one materialized extraction job."""

from __future__ import annotations

from typing import Any, Protocol

from extraction.domain.extraction_job import ExtractionJobRecord


class IExtractionJobRunner(Protocol):
    """Runs one extraction job and returns completion metrics."""

    async def run(self, job: ExtractionJobRecord, *, tenant_id: str) -> dict[str, Any]:
        """Execute the job and return token/cost/write metrics."""
        ...
