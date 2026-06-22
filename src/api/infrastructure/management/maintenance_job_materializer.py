"""Materialize by-files maintenance extraction jobs from changed source files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from ulid import ULID

from extraction.domain.extraction_job import (
    ExtractionJobRecord,
    ExtractionJobStatus,
    ExtractionTargetFile,
)

MAINTENANCE_JOB_SET_NAME = "maintenance"
_DEFAULT_MAINTENANCE_DESCRIPTION = (
    "Update the knowledge graph to reflect upstream source changes since the last "
    "extraction baseline. Consider all entity types, relationship instances, and "
    "ontology constraints so the graph stays accurate."
)


@dataclass(frozen=True)
class ChangedMaintenanceFile:
    """One changed repository file eligible for a maintenance extraction job."""

    data_source_id: str
    repository_folder: str
    path: str
    status: str
    package_id: str
    baseline_commit: str
    head_commit: str
    patch: str | None = None


def _batch_items(
    items: Sequence[ChangedMaintenanceFile], batch_size: int
) -> list[list[ChangedMaintenanceFile]]:
    size = max(1, batch_size)
    materialized = list(items)
    return [list(materialized[i : i + size]) for i in range(0, len(materialized), size)]


def _generate_job_id(batch_idx: int, content_hash: str) -> str:
    hash_suffix = hashlib.sha256(content_hash.encode()).hexdigest()[:8]
    return f"{MAINTENANCE_JOB_SET_NAME}_batch_{batch_idx:04d}_{hash_suffix}"


def _build_maintenance_description(
    changed_files: Sequence[ChangedMaintenanceFile],
) -> str:
    lines = [_DEFAULT_MAINTENANCE_DESCRIPTION, "", "## Changed files in this job"]
    for changed in changed_files:
        lines.append(f"- [{changed.status}] {changed.repository_folder}/{changed.path}")
        if changed.patch:
            lines.extend(
                ["", f"### Diff: {changed.path}", "```diff", changed.patch, "```"]
            )
    lines.extend(
        [
            "",
            "## Scope",
            "Each changed file is materialized under repository-files/ using commit-first paths:",
            "- Baseline snapshot (last extraction): repository-files/{baseline_commit}/{repo}/{path}",
            "- Current HEAD snapshot: repository-files/{head_commit}/{repo}/{path}",
            "- Unified diff (when available): repository-files/diffs/{baseline}..{head}/{repo}/{path}.patch",
            "Read job-context.json target_files for per-file commits and diff paths. Use the "
            "baseline copy to understand prior graph context and the HEAD copy for the updated "
            "source of truth. Read the live graph via workload-graph-read helpers, and emit "
            "JSONL mutations that keep every affected entity and relationship accurate.",
        ]
    )
    return "\n".join(lines)


def materialize_maintenance_jobs(
    *,
    knowledge_graph_id: str,
    changed_files: Sequence[ChangedMaintenanceFile],
    files_per_job: int,
) -> list[ExtractionJobRecord]:
    """Build pending maintenance jobs batched across all changed files on a KG."""
    if not changed_files:
        return []

    jobs: list[ExtractionJobRecord] = []
    for batch_idx, batch in enumerate(
        _batch_items(changed_files, files_per_job), start=1
    ):
        content_hash = "|".join(
            f"{item.repository_folder}:{item.path}:{item.status}" for item in batch
        )
        target_files = tuple(
            ExtractionTargetFile(
                path=item.path,
                repository_folder=item.repository_folder,
                package_id=item.package_id,
                baseline_commit=item.baseline_commit,
                head_commit=item.head_commit,
                change_status=item.status,
                patch=item.patch,
                data_source_id=item.data_source_id,
            )
            for item in batch
        )
        jobs.append(
            ExtractionJobRecord(
                id=str(ULID()),
                knowledge_graph_id=knowledge_graph_id,
                job_id=_generate_job_id(batch_idx, content_hash),
                job_set_name=MAINTENANCE_JOB_SET_NAME,
                strategy="by_files",
                status=ExtractionJobStatus.PENDING,
                order_index=batch_idx - 1,
                description=_build_maintenance_description(batch),
                target_files=target_files,
            )
        )
    return jobs
