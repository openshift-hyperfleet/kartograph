"""Execute one materialized extraction job."""

from __future__ import annotations

import asyncio
from typing import Any

from extraction.domain.extraction_job import ExtractionJobRecord


class ExtractionJobExecutor:
    """Runs one extraction job using per-instance description guidance."""

    async def execute(self, job: ExtractionJobRecord) -> dict[str, Any]:
        """Process target instances for one job.

        The sticky extraction agent container path will replace this stub with
        a full Claude Agent SDK turn scoped to ``job.description`` and the
        assigned instance slugs. For now we simulate successful completion so
        orchestration, status APIs, and UI can be exercised end-to-end.
        """
        await asyncio.sleep(0.05)
        instance_count = len(job.target_instances)
        return {
            "input_tokens": 100 * instance_count,
            "output_tokens": 50 * instance_count,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": 0.001 * instance_count,
            "entities_created": 0,
            "entities_modified": instance_count,
            "relationships_created": 0,
        }
