"""Shape archived extraction jobs for mutation history UI."""

from __future__ import annotations

from typing import Any

from extraction.domain.extraction_job import ExtractionJobRecord


def archived_job_write_ops(job: ExtractionJobRecord) -> int:
    """Return write op count, including DELETE lines for graph-management sessions."""
    if job.strategy == "graph_management_session" and job.applied_mutations_jsonl:
        from extraction.domain.mutation_jsonl_metrics import metrics_from_mutation_jsonl

        return int(
            metrics_from_mutation_jsonl(job.applied_mutations_jsonl).get("write_ops")
            or 0
        )
    return job.write_ops()


def serialize_archived_job(job: ExtractionJobRecord) -> dict[str, Any]:
    return {
        **job.to_dict(),
        "jobId": job.job_id,
        "jobSet": job.job_set_name,
        "writeOps": archived_job_write_ops(job),
        "hasMutations": bool(job.applied_mutations_jsonl),
        "hasInstanceChanges": bool(job.applied_instance_changes_jsonl),
        "inputTokens": job.input_tokens,
        "outputTokens": job.output_tokens,
        "costUsd": job.cost_usd,
        "entitiesCreated": job.entities_created,
        "entitiesModified": job.entities_modified,
        "relationshipsCreated": job.relationships_created,
        "relationshipsModified": job.relationships_modified,
        "archivedAt": job.archived_at.isoformat() if job.archived_at else None,
        "strategy": job.strategy,
    }


def group_archived_jobs_by_run_and_set(
    jobs: list[ExtractionJobRecord],
) -> list[dict[str, Any]]:
    """Group archived jobs by extraction run start, then job set name."""
    runs: dict[str, dict[str, Any]] = {}
    for job in jobs:
        run_key = (
            job.run_started_at.isoformat() if job.run_started_at else "unknown-run"
        )
        if run_key not in runs:
            runs[run_key] = {
                "runStartedAt": job.run_started_at.isoformat()
                if job.run_started_at
                else None,
                "jobSets": {},
                "jobCount": 0,
                "writeOps": 0,
                "inputTokens": 0,
                "outputTokens": 0,
                "costUsd": 0.0,
            }
        run = runs[run_key]
        set_name = job.job_set_name
        job_sets: dict[str, list[dict[str, Any]]] = run["jobSets"]
        if set_name not in job_sets:
            job_sets[set_name] = []
        job_sets[set_name].append(serialize_archived_job(job))
        run["jobCount"] += 1
        run["writeOps"] += archived_job_write_ops(job)
        run["inputTokens"] += job.input_tokens
        run["outputTokens"] += job.output_tokens
        run["costUsd"] += job.cost_usd

    grouped: list[dict[str, Any]] = []
    for run_key in sorted(runs.keys(), reverse=True):
        run = runs[run_key]
        job_sets_payload = []
        for set_name in sorted(run["jobSets"].keys()):
            archived_jobs = run["jobSets"][set_name]
            job_sets_payload.append(
                {
                    "jobSet": set_name,
                    "jobs": archived_jobs,
                    "jobCount": len(archived_jobs),
                    "writeOps": sum(
                        int(job.get("writeOps") or 0) for job in archived_jobs
                    ),
                }
            )
        grouped.append(
            {
                "runStartedAt": run["runStartedAt"],
                "jobCount": run["jobCount"],
                "writeOps": run["writeOps"],
                "inputTokens": run["inputTokens"],
                "outputTokens": run["outputTokens"],
                "costUsd": round(float(run["costUsd"]), 6),
                "jobSets": job_sets_payload,
            }
        )
    return grouped
