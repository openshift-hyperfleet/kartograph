#!/usr/bin/env python3
"""Convert entity scanner JSON to Kartograph CREATE JSONL (batch apply).

Input JSON array (from ``{label}.py`` scanner stdout):

  [{"slug": "my-entity", "properties": {"name": "My Entity", ...}}, ...]

Example:

  python3 instance_generators/test.py repository-files \\
    > instance_generators/out/test_instances.json

  python3 instance_generators/entities_to_jsonl.py test \\
    --data-source-id schema-bootstrap \\
    instance_generators/out/test_instances.json \\
    > instance_generators/out/test_instances.jsonl

  # kartograph_validate_graph_mutations_from_file → apply-from-file (one batch).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def deterministic_node_id(*, entity_label: str, slug: str, tenant_id: str = "") -> str:
    """Stable node id prefix — normalized to lowercase for deterministic hashing."""
    normalized_type = entity_label.strip().lower()
    combined = f"{tenant_id}:{normalized_type}:{slug.strip()}"
    digest = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f"{normalized_type}:{digest}"


def mutation_entity_label(entity_label: str) -> str:
    """Return the CREATE label — must match ontology ``label`` exactly (case-sensitive)."""
    return entity_label.strip()


def instance_to_create_line(
    *,
    entity_label: str,
    slug: str,
    properties: dict[str, Any],
    data_source_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    set_properties = dict(properties)
    set_properties.setdefault("slug", slug)
    set_properties.setdefault("name", slug)
    set_properties["data_source_id"] = data_source_id
    return {
        "op": "CREATE",
        "type": "node",
        "id": deterministic_node_id(
            entity_label=entity_label,
            slug=slug,
            tenant_id=tenant_id,
        ),
        "label": mutation_entity_label(entity_label),
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
        description="Convert entity scanner JSON to Kartograph node CREATE JSONL.",
    )
    parser.add_argument(
        "entity_label",
        help="Entity type label matching ontology exactly (case-sensitive, e.g. APIEndpoint).",
    )
    parser.add_argument("input", nargs="?", help="Path to JSON file; omit to read stdin.")
    parser.add_argument("--tenant-id", default="", help="Tenant id for deterministic node ids.")
    parser.add_argument("--data-source-id", default="schema-bootstrap")
    args = parser.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
    instances = load_instances(json.loads(raw))
    for row in instances:
        line = instance_to_create_line(
            entity_label=args.entity_label,
            slug=row["slug"],
            properties=row["properties"],
            data_source_id=args.data_source_id,
            tenant_id=args.tenant_id,
        )
        sys.stdout.write(json.dumps(line, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
