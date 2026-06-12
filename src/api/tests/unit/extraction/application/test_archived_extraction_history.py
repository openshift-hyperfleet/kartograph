"""Unit tests for archived extraction history grouping."""

from __future__ import annotations

from datetime import UTC, datetime

from extraction.application.archived_extraction_history import group_archived_jobs_by_run_and_set
from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionJobStatus


def _job(
    *,
    job_id: str,
    job_set: str,
    run_started_at: datetime,
) -> ExtractionJobRecord:
    return ExtractionJobRecord(
        id="01JOB",
        knowledge_graph_id="01KG",
        job_id=job_id,
        job_set_name=job_set,
        strategy="by_instances",
        status=ExtractionJobStatus.ARCHIVED,
        order_index=0,
        description="",
        entities_modified=2,
        run_started_at=run_started_at,
        archived_at=run_started_at,
        applied_mutations_jsonl='{"op":"UPDATE","type":"node"}',
    )


def test_group_archived_jobs_by_run_and_set() -> None:
    run_a = datetime(2026, 6, 12, 18, 0, tzinfo=UTC)
    run_b = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)
    grouped = group_archived_jobs_by_run_and_set(
        [
            _job(job_id="job-a1", job_set="Adapter Deep Extraction", run_started_at=run_a),
            _job(job_id="job-a2", job_set="Adapter Deep Extraction", run_started_at=run_a),
            _job(job_id="job-b1", job_set="Resource Extraction", run_started_at=run_b),
        ]
    )

    assert len(grouped) == 2
    assert grouped[0]["jobCount"] == 2
    assert grouped[0]["jobSets"][0]["jobSet"] == "Adapter Deep Extraction"
    assert grouped[1]["jobCount"] == 1
