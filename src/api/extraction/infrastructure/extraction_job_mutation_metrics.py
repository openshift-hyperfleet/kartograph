"""Count graph instance write operations from applied extraction job JSONL."""

from __future__ import annotations

from pathlib import Path

from extraction.domain.mutation_jsonl_metrics import metrics_from_mutation_jsonl

__all__ = [
    "applied_mutation_jsonl_from_workdir",
    "metrics_from_mutation_jsonl",
    "metrics_from_mutation_workdir",
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
