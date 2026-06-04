#!/usr/bin/env python3
"""Convert generator JSON output to Kartograph CREATE JSONL (entity nodes).

Reads a JSON array from a file or stdin:

  [{"slug": "my-entity", "properties": {"name": "My Entity", ...}}, ...]

Writes one CREATE line per instance, sorted by slug. Node ids are deterministic from
entity label + slug (SHA256, same algorithm as the platform EntityIdGenerator with
an empty tenant scope unless --tenant-id is passed).

Example:

  python3 instance_generators/source_file.py repository-files \\
    > instance_generators/out/files.json

  python3 instance_generators/json_instances_to_jsonl.py source_file \\
    --data-source-id schema-bootstrap \\
    --source-path graph-management-assistant \\
    instance_generators/out/files.json \\
    > instance_generators/out/files.jsonl

  # Then validate and apply via Kartograph schema tools (from-file).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def deterministic_node_id(*, entity_label: str, slug: str, tenant_id: str = "") -> str:
    normalized_type = entity_label.strip().lower()
    combined = f"{tenant_id}:{normalized_type}:{slug.strip()}"
    digest = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f"{normalized_type}:{digest}"


def instance_to_create_line(
    *,
    entity_label: str,
    slug: str,
    properties: dict[str, Any],
    data_source_id: str,
    source_path: str,
    tenant_id: str,
) -> dict[str, Any]:
    set_properties = dict(properties)
    set_properties.setdefault("slug", slug)
    set_properties.setdefault("name", slug)
    set_properties["data_source_id"] = data_source_id
    set_properties["source_path"] = source_path
    return {
        "op": "CREATE",
        "type": "node",
        "id": deterministic_node_id(
            entity_label=entity_label,
            slug=slug,
            tenant_id=tenant_id,
        ),
        "label": entity_label.strip().lower(),
        "set_properties": set_properties,
    }


def load_instances(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Generator output must be a JSON array")
    instances: list[dict[str, Any]] = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"Instance at index {index} must be an object")
        slug = row.get("slug")
        if not slug or not str(slug).strip():
            raise ValueError(f"Instance at index {index} is missing slug")
        properties = row.get("properties") or {}
        if not isinstance(properties, dict):
            raise ValueError(f"Instance at index {index} properties must be an object")
        instances.append({"slug": str(slug).strip(), "properties": properties})
    return sorted(instances, key=lambda item: item["slug"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert generator JSON array to Kartograph node CREATE JSONL.",
    )
    parser.add_argument(
        "entity_label",
        help="Entity type label in the ontology (e.g. source_file, folder).",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to JSON file; omit to read stdin.",
    )
    parser.add_argument(
        "--tenant-id",
        default="",
        help="Tenant id for deterministic node ids (optional).",
    )
    parser.add_argument(
        "--data-source-id",
        default="schema-bootstrap",
        help="data_source_id stamped on each CREATE line.",
    )
    parser.add_argument(
        "--source-path",
        default="graph-management-assistant",
        help="source_path stamped on each CREATE line.",
    )
    args = parser.parse_args()

    if args.input:
        raw = Path(args.input).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    instances = load_instances(json.loads(raw))
    for row in instances:
        line = instance_to_create_line(
            entity_label=args.entity_label,
            slug=row["slug"],
            properties=row["properties"],
            data_source_id=args.data_source_id,
            source_path=args.source_path,
            tenant_id=args.tenant_id,
        )
        sys.stdout.write(json.dumps(line, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
