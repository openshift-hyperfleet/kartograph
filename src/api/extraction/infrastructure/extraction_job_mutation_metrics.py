"""Count graph instance write operations from applied extraction job JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph.domain.value_objects import EntityType, MutationOperationType


def metrics_from_mutation_jsonl(jsonl_content: str) -> dict[str, int]:
    """Count instance CREATE/UPDATE operations; ignore schema DEFINE operations."""
    entities_created = 0
    entities_modified = 0
    relationships_created = 0
    relationships_modified = 0

    for raw_line in jsonl_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue

        op = str(row.get("op") or "").upper()
        entity_type = str(row.get("type") or "").lower()
        if op == MutationOperationType.DEFINE.value:
            continue
        if op not in {
            MutationOperationType.CREATE.value,
            MutationOperationType.UPDATE.value,
        }:
            continue

        if entity_type == EntityType.NODE.value:
            if op == MutationOperationType.CREATE.value:
                entities_created += 1
            else:
                entities_modified += 1
        elif entity_type == EntityType.EDGE.value:
            if op == MutationOperationType.CREATE.value:
                relationships_created += 1
            else:
                relationships_modified += 1

    write_ops = (
        entities_created
        + entities_modified
        + relationships_created
        + relationships_modified
    )
    return {
        "entities_created": entities_created,
        "entities_modified": entities_modified,
        "relationships_created": relationships_created,
        "relationships_modified": relationships_modified,
        "write_ops": write_ops,
    }


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
        "relationships_created": 0,
        "relationships_modified": 0,
        "write_ops": 0,
    }
