"""Unit tests for archived extraction history grouping."""

from __future__ import annotations

from datetime import UTC, datetime

from extraction.application.archived_extraction_history import (
    group_archived_jobs_by_run_and_set,
    serialize_archived_job,
)
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
            _job(
                job_id="job-a1", job_set="Adapter Deep Extraction", run_started_at=run_a
            ),
            _job(
                job_id="job-a2", job_set="Adapter Deep Extraction", run_started_at=run_a
            ),
            _job(job_id="job-b1", job_set="Resource Extraction", run_started_at=run_b),
        ]
    )

    assert len(grouped) == 2
    assert grouped[0]["jobCount"] == 2
    assert grouped[0]["jobSets"][0]["jobSet"] == "Adapter Deep Extraction"
    assert grouped[1]["jobCount"] == 1


def test_serialize_archived_job_includes_camel_case_metrics() -> None:
    job = ExtractionJobRecord(
        id="01JOB",
        knowledge_graph_id="01KG",
        job_id="gma-session-1",
        job_set_name="Graph Management · One-off Mutations",
        strategy="graph_management_session",
        status=ExtractionJobStatus.ARCHIVED,
        order_index=0,
        description="",
        input_tokens=1200,
        output_tokens=400,
        cost_usd=0.45,
        entities_modified=2,
        applied_mutations_jsonl='{"op":"UPDATE","type":"node","id":"adapter:abc"}',
    )

    payload = serialize_archived_job(job)

    assert payload["inputTokens"] == 1200
    assert payload["outputTokens"] == 400
    assert payload["costUsd"] == 0.45
    assert payload["entitiesCreated"] == 0
    assert payload["entitiesModified"] == 2
    assert payload["strategy"] == "graph_management_session"
