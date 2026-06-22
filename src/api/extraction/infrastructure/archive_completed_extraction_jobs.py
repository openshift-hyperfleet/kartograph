"""Promote completed extraction jobs into archived history with metric backfill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionJobStatus
from extraction.infrastructure.extraction_job_activity import job_workdir
from extraction.infrastructure.extraction_job_mutation_metrics import (
    reconcile_mutation_metrics,
)
from extraction.infrastructure.extraction_job_verdict import load_mutation_verdict
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
)


def backfill_archival_metrics(
    job: ExtractionJobRecord,
    *,
    workdir: Path,
) -> dict[str, Any]:
    """Recompute graph write metrics from a persisted job workdir before archival."""
    base = {
        "entities_created": job.entities_created,
        "entities_modified": job.entities_modified,
        "relationships_created": job.relationships_created,
        "relationships_modified": job.relationships_modified,
    }
    verdict = load_mutation_verdict(workdir)
    operations_applied = verdict.operations_applied if verdict else 0
    return reconcile_mutation_metrics(
        base,
        workdir=workdir,
        operations_applied=operations_applied,
    )


async def archive_completed_extraction_jobs(
    *,
    repository: ExtractionJobRepository,
    knowledge_graph_id: str,
    settings: ExtractionWorkloadRuntimeSettings,
) -> dict[str, int]:
    """Move all completed jobs to archived, backfilling metrics from workdirs when possible."""
    jobs = await repository.list_jobs_by_status(
        knowledge_graph_id=knowledge_graph_id,
        status=ExtractionJobStatus.COMPLETED,
    )
    archived_count = 0
    metrics_backfilled_count = 0
    for job in jobs:
        workdir = job_workdir(
            knowledge_graph_id=job.knowledge_graph_id,
            job_id=job.job_id,
            settings=settings,
        )
        metrics = backfill_archival_metrics(job, workdir=workdir)
        prior_write_ops = job.write_ops()
        new_write_ops = int(metrics.get("write_ops") or 0)
        if new_write_ops > prior_write_ops:
            metrics_backfilled_count += 1
        promoted = await repository.promote_completed_job_to_archived(
            knowledge_graph_id=knowledge_graph_id,
            job_id=job.job_id,
            metrics=metrics,
        )
        if promoted:
            archived_count += 1
    return {
        "archived_count": archived_count,
        "metrics_backfilled_count": metrics_backfilled_count,
    }
