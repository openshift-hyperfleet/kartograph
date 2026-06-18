"""Structured before/after snapshots for applied graph instance mutations."""

from __future__ import annotations

import json
from typing import Any


def serialize_instance_snapshot(
    *,
    instance_id: str,
    label: str,
    entity_kind: str,
    properties: dict[str, Any] | None,
    start_id: str | None = None,
    end_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": instance_id,
        "label": label,
        "type": entity_kind,
        "properties": dict(properties or {}),
    }
    if start_id is not None:
        payload["start_id"] = start_id
    if end_id is not None:
        payload["end_id"] = end_id
    return payload


def property_changes(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return per-property before/after rows for one instance snapshot pair."""
    before_props = dict(before or {})
    after_props = dict(after or {})
    keys = sorted(set(before_props) | set(after_props))
    changes: list[dict[str, Any]] = []
    for key in keys:
        old_value = before_props.get(key)
        new_value = after_props.get(key)
        if old_value == new_value:
            continue
        changes.append({"key": key, "before": old_value, "after": new_value})
    return changes


def build_instance_change_record(
    *,
    op: str,
    entity_kind: str,
    instance_id: str,
    label: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    start_id: str | None = None,
    end_id: str | None = None,
) -> dict[str, Any]:
    before_snapshot = (
        serialize_instance_snapshot(
            instance_id=instance_id,
            label=str(label or ""),
            entity_kind=entity_kind,
            properties=before,
            start_id=start_id,
            end_id=end_id,
        )
        if before is not None
        else None
    )
    after_snapshot = (
        serialize_instance_snapshot(
            instance_id=instance_id,
            label=str(label or ""),
            entity_kind=entity_kind,
            properties=after,
            start_id=start_id,
            end_id=end_id,
        )
        if after is not None
        else None
    )
    return {
        "op": op.upper(),
        "type": entity_kind,
        "id": instance_id,
        "label": label,
        "start_id": start_id,
        "end_id": end_id,
        "before": before_snapshot,
        "after": after_snapshot,
        "property_changes": property_changes(before, after),
    }


def instance_changes_to_jsonl(records: list[dict[str, Any]]) -> str:
    return "\n".join(
        json.dumps(record, separators=(",", ":"), sort_keys=True) for record in records
    )


def parse_instance_changes_jsonl(jsonl_content: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_line in jsonl_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            records.append(row)
    return records
