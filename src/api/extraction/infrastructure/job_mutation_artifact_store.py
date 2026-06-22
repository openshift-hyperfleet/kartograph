"""Persist applied mutation artifacts from extraction job workload runs."""

from __future__ import annotations

from pathlib import Path

from extraction.infrastructure.extraction_job_activity import job_workdir
from extraction.infrastructure.extraction_job_workdir_layout import mutation_result_path
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)

APPLIED_MUTATIONS_FILENAME = "applied.jsonl"
INSTANCE_CHANGES_FILENAME = "instance-changes.jsonl"


def append_job_mutation_artifacts(
    *,
    knowledge_graph_id: str,
    job_id: str,
    applied_jsonl: str | None = None,
    instance_changes_jsonl: str | None = None,
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> None:
    """Append applied JSONL and instance change records to a job workdir."""
    workdir = job_workdir(
        knowledge_graph_id=knowledge_graph_id,
        job_id=job_id,
        settings=settings or get_extraction_workload_runtime_settings(),
    )
    mutations_dir = workdir / "mutations"
    mutations_dir.mkdir(parents=True, exist_ok=True)
    mutation_result_path(workdir).parent.mkdir(parents=True, exist_ok=True)

    if applied_jsonl and applied_jsonl.strip():
        _append_lines(mutations_dir / APPLIED_MUTATIONS_FILENAME, applied_jsonl.strip())
    if instance_changes_jsonl and instance_changes_jsonl.strip():
        _append_lines(
            mutations_dir / INSTANCE_CHANGES_FILENAME, instance_changes_jsonl.strip()
        )


def read_instance_changes_from_workdir(
    job_root: Path,
) -> str | None:
    path = job_root / "mutations" / INSTANCE_CHANGES_FILENAME
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8").strip()
    return content or None


def _append_lines(path: Path, chunk: str) -> None:
    existing = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
    combined = "\n".join(part for part in (existing, chunk) if part)
    path.write_text(combined + ("\n" if combined else ""), encoding="utf-8")
