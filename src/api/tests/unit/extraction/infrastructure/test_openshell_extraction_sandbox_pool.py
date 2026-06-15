"""Unit tests for OpenShell per-worker extraction sandboxes."""

from __future__ import annotations

from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionJobStatus
from extraction.infrastructure.openshell.extraction_sandbox_pool import (
    resolve_extraction_sandbox_assignment,
    worker_index,
)
from extraction.infrastructure.workload_runtime_settings import ExtractionWorkloadRuntimeSettings


def _job(*, job_id: str = "job-a", worker_id: str | None = "worker-03") -> ExtractionJobRecord:
    return ExtractionJobRecord(
        id="01JOB",
        knowledge_graph_id="01KG1234567890",
        job_id=job_id,
        job_set_name="adapters",
        strategy="by_files",
        status=ExtractionJobStatus.IN_PROGRESS,
        order_index=0,
        description="test",
        worker_id=worker_id,
    )


def test_worker_index_parses_worker_ids() -> None:
    assert worker_index("worker-01") == 1
    assert worker_index("worker-12") == 12
    assert worker_index(None) == 1


def test_resolve_assignment_uses_one_sandbox_per_worker() -> None:
    settings = ExtractionWorkloadRuntimeSettings(job_runner="openshell")

    worker_03 = resolve_extraction_sandbox_assignment(_job(worker_id="worker-03"), settings)
    worker_07 = resolve_extraction_sandbox_assignment(_job(job_id="job-b", worker_id="worker-07"), settings)

    assert worker_03.reuse is True
    assert worker_03.slot == 3
    assert worker_03.sandbox_name.endswith("-w03")
    assert worker_07.sandbox_name.endswith("-w07")
    assert worker_03.sandbox_name != worker_07.sandbox_name
