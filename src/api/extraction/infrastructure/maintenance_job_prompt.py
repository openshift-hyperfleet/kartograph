"""Prompt builders for maintenance extraction jobs."""

from __future__ import annotations

from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.infrastructure.extraction_job_prompt import build_extraction_job_prompt
from infrastructure.management.maintenance_job_materializer import MAINTENANCE_JOB_SET_NAME


def build_job_run_prompt(*, job: ExtractionJobRecord) -> str:
    """Return the agent prompt for one extraction or maintenance job."""
    if job.job_set_name == MAINTENANCE_JOB_SET_NAME:
        return build_maintenance_job_prompt(job=job)
    return build_extraction_job_prompt(job=job)


def build_maintenance_job_prompt(*, job: ExtractionJobRecord) -> str:
    """Return a maintenance-specific prompt with diff-aware file instructions."""
    base = build_extraction_job_prompt(job=job)
    return (
        f"{base}\n\n"
        "## Maintenance objective\n"
        "These repository files changed since the last extraction baseline. Compare the "
        "baseline snapshot (last successful extraction commit) with the HEAD snapshot "
        "(current branch tip). Read unified diffs under repository-files/diffs/ when "
        "present. Use that evidence plus the live graph to update existing instances and "
        "relationships. Do not limit updates to only the files' local entities — reconcile "
        "downstream references across the entire knowledge graph schema."
    )
