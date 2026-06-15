"""Unit tests for promoting completed extraction jobs into archived history."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from extraction.application.archive_completed_extraction_jobs import (
    archive_completed_extraction_jobs,
    backfill_archival_metrics,
)
from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionJobStatus
from extraction.infrastructure.workload_runtime_settings import ExtractionWorkloadRuntimeSettings


def _completed_job(*, job_id: str = "job-1") -> ExtractionJobRecord:
    return ExtractionJobRecord(
        id="01JOB",
        knowledge_graph_id="kg-1",
        job_id=job_id,
        job_set_name="adapters",
        strategy="per_instance",
        status=ExtractionJobStatus.COMPLETED,
        order_index=0,
        description="test job",
    )


def test_backfill_archival_metrics_reads_jsonl_and_result_json(tmp_path: Path) -> None:
    job = _completed_job()
    mutations = tmp_path / "mutations"
    mutations.mkdir()
    (mutations / "batch.jsonl").write_text(
        json.dumps(
            {
                "op": "UPDATE",
                "type": "node",
                "id": "adapter:1",
                "label": "Adapter",
                "set_properties": {"description": "updated"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (mutations / "result.json").write_text(
        json.dumps({"action": "apply", "applied": True, "operations_applied": 3}),
        encoding="utf-8",
    )

    metrics = backfill_archival_metrics(job, workdir=tmp_path)

    assert metrics["entities_modified"] == 1
    assert metrics["write_ops"] == 1
    assert metrics["applied_mutations_jsonl"]


def test_backfill_archival_metrics_falls_back_to_operations_applied(tmp_path: Path) -> None:
    job = _completed_job()
    mutations = tmp_path / "mutations"
    mutations.mkdir()
    (mutations / "result.json").write_text(
        json.dumps({"action": "apply", "applied": True, "operations_applied": 3}),
        encoding="utf-8",
    )

    metrics = backfill_archival_metrics(job, workdir=tmp_path)

    assert metrics["entities_modified"] == 3
    assert metrics["write_ops"] == 3


class _FakeRepository:
    def __init__(self, jobs: list[ExtractionJobRecord]) -> None:
        self._jobs = list(jobs)
        self.promoted: list[tuple[str, dict]] = []

    async def list_jobs_by_status(
        self,
        *,
        knowledge_graph_id: str,
        status: ExtractionJobStatus,
        limit: int = 10_000,
    ) -> list[ExtractionJobRecord]:
        assert knowledge_graph_id == "kg-1"
        assert status == ExtractionJobStatus.COMPLETED
        return list(self._jobs)

    async def promote_completed_job_to_archived(
        self,
        *,
        knowledge_graph_id: str,
        job_id: str,
        metrics: dict,
    ) -> bool:
        self.promoted.append((job_id, metrics))
        return True


@pytest.mark.asyncio
async def test_archive_completed_extraction_jobs_promotes_all_completed(tmp_path: Path) -> None:
    job = _completed_job()
    work_root = tmp_path / "kg-1" / job.job_id
    mutations = work_root / "mutations"
    mutations.mkdir(parents=True)
    (mutations / "result.json").write_text(
        json.dumps({"action": "apply", "applied": True, "operations_applied": 2}),
        encoding="utf-8",
    )
    repo = _FakeRepository([job])
    settings = ExtractionWorkloadRuntimeSettings(
        backend="openshell",
        container_engine="docker",
        extraction_job_work_dir=str(tmp_path),
    )

    result = await archive_completed_extraction_jobs(
        repository=repo,
        knowledge_graph_id="kg-1",
        settings=settings,
    )

    assert result["archived_count"] == 1
    assert result["metrics_backfilled_count"] == 1
    assert repo.promoted[0][0] == "job-1"
    assert repo.promoted[0][1]["write_ops"] == 2
