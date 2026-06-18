"""Count graph instance write operations from applied extraction job JSONL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from extraction.domain.mutation_jsonl_metrics import metrics_from_mutation_jsonl
from extraction.infrastructure.job_mutation_artifact_store import read_instance_changes_from_workdir

__all__ = [
    "applied_mutation_jsonl_from_workdir",
    "metrics_from_mutation_jsonl",
    "metrics_from_mutation_workdir",
    "reconcile_mutation_metrics",
]


def metrics_from_mutation_workdir(job_root: Path) -> dict[str, int]:
    """Load graph write metrics from mutations/*.jsonl in a job workspace."""
    mutations_dir = job_root / "mutations"
    if not mutations_dir.is_dir():
        return _empty_metrics()

    jsonl_files = sorted(
        path for path in mutations_dir.glob("*.jsonl") if path.is_file()
    )
    if not jsonl_files:
        return _empty_metrics()

    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in jsonl_files
    )
    return metrics_from_mutation_jsonl(combined)


def applied_mutation_jsonl_from_workdir(job_root: Path) -> str | None:
    """Return concatenated applied JSONL content for archival."""
    mutations_dir = job_root / "mutations"
    if not mutations_dir.is_dir():
        return None
    jsonl_files = sorted(path for path in mutations_dir.glob("*.jsonl") if path.is_file())
    if not jsonl_files:
        return None
    parts = [path.read_text(encoding="utf-8") for path in jsonl_files]
    content = "\n".join(part.rstrip("\n") for part in parts if part.strip())
    return content or None


def reconcile_mutation_metrics(
    metrics: dict[str, Any],
    *,
    workdir: Path,
    operations_applied: int,
) -> dict[str, Any]:
    """Ensure graph write counters align with applied mutation batches."""
    merged = dict(metrics)
    if int(merged.get("write_ops", 0)) > 0:
        return merged

    workdir_metrics = metrics_from_mutation_workdir(workdir)
    if int(workdir_metrics.get("write_ops", 0)) > 0:
        merged.update(workdir_metrics)
        applied_jsonl = applied_mutation_jsonl_from_workdir(workdir)
        if applied_jsonl:
            merged["applied_mutations_jsonl"] = applied_jsonl
        instance_changes_jsonl = read_instance_changes_from_workdir(workdir)
        if instance_changes_jsonl:
            merged["applied_instance_changes_jsonl"] = instance_changes_jsonl
        return merged

    if operations_applied > 0:
        merged["entities_modified"] = operations_applied
        merged["write_ops"] = operations_applied
    return merged


def _empty_metrics() -> dict[str, int]:
    return {
        "entities_created": 0,
        "entities_modified": 0,
        "entities_deleted": 0,
        "relationships_created": 0,
        "relationships_modified": 0,
        "relationships_deleted": 0,
        "write_ops": 0,
    }
