"""Count graph write operations from applied mutation JSONL."""

from __future__ import annotations

import json


def metrics_from_mutation_jsonl(jsonl_content: str) -> dict[str, int]:
    """Count instance CREATE/UPDATE/DELETE operations; ignore schema DEFINE operations."""
    entities_created = 0
    entities_modified = 0
    entities_deleted = 0
    relationships_created = 0
    relationships_modified = 0
    relationships_deleted = 0

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
        if op == "DEFINE":
            continue
        if op not in {"CREATE", "UPDATE", "DELETE"}:
            continue

        if entity_type == "node":
            if op == "CREATE":
                entities_created += 1
            elif op == "UPDATE":
                entities_modified += 1
            else:
                entities_deleted += 1
        elif entity_type == "edge":
            if op == "CREATE":
                relationships_created += 1
            elif op == "UPDATE":
                relationships_modified += 1
            else:
                relationships_deleted += 1

    write_ops = (
        entities_created
        + entities_modified
        + entities_deleted
        + relationships_created
        + relationships_modified
        + relationships_deleted
    )
    return {
        "entities_created": entities_created,
        "entities_modified": entities_modified,
        "entities_deleted": entities_deleted,
        "relationships_created": relationships_created,
        "relationships_modified": relationships_modified,
        "relationships_deleted": relationships_deleted,
        "write_ops": write_ops,
    }
