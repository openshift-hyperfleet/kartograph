#!/usr/bin/env python3
"""Convert relationship scanner JSON to Kartograph edge CREATE JSONL (batch apply).

Input JSON array:

  [{"source_slug": "repo-a", "target_slug": "test-b", "properties": {}}]

Run after entity nodes exist. Author primary direction only; platform creates twin inverse edges.

Example:

  python3 instance_generators/repository_defines_test.py repository-files \\
    > instance_generators/out/repository_defines_test_instances.json

  python3 instance_generators/relationships_to_jsonl.py defines repository test \\
    instance_generators/out/repository_defines_test_instances.json \\
    > instance_generators/out/repository_defines_test_instances.jsonl
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


def deterministic_edge_id(
    *,
    relationship_label: str,
    start_id: str,
    end_id: str,
    tenant_id: str = "",
) -> str:
    normalized_label = relationship_label.strip().lower()
    combined = f"{tenant_id}:{start_id.strip()}:{normalized_label}:{end_id.strip()}"
    digest = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f"{normalized_label}:{digest}"


def mutation_relationship_label(relationship_label: str) -> str:
    """Return the CREATE label — must match ontology ``label`` exactly (case-sensitive)."""
    return relationship_label.strip()


def relationship_to_create_line(
    *,
    relationship_label: str,
    source_entity_type: str,
    target_entity_type: str,
    source_slug: str,
    target_slug: str,
    properties: dict[str, Any],
    data_source_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    start_id = deterministic_node_id(
        entity_label=source_entity_type,
        slug=source_slug,
        tenant_id=tenant_id,
    )
    end_id = deterministic_node_id(
        entity_label=target_entity_type,
        slug=target_slug,
        tenant_id=tenant_id,
    )
    set_properties = dict(properties)
    set_properties["data_source_id"] = data_source_id
    return {
        "op": "CREATE",
        "type": "edge",
        "id": deterministic_edge_id(
            relationship_label=relationship_label,
            start_id=start_id,
            end_id=end_id,
            tenant_id=tenant_id,
        ),
        "label": mutation_relationship_label(relationship_label),
        "start_id": start_id,
        "end_id": end_id,
        "set_properties": set_properties,
    }


def load_relationships(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Generator output must be a JSON array")
    relationships: list[dict[str, Any]] = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"Relationship at index {index} must be an object")
        source_slug = row.get("source_slug")
        target_slug = row.get("target_slug")
        if not source_slug or not str(source_slug).strip():
            raise ValueError(f"Relationship at index {index} is missing source_slug")
        if not target_slug or not str(target_slug).strip():
            raise ValueError(f"Relationship at index {index} is missing target_slug")
        properties = row.get("properties") or {}
        if not isinstance(properties, dict):
            raise ValueError(
                f"Relationship at index {index} properties must be an object"
            )
        relationships.append(
            {
                "source_slug": str(source_slug).strip(),
                "target_slug": str(target_slug).strip(),
                "properties": properties,
            }
        )
    return sorted(
        relationships,
        key=lambda item: (item["source_slug"], item["target_slug"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert relationship scanner JSON to Kartograph edge CREATE JSONL.",
    )
    parser.add_argument(
        "relationship_label",
        help="Relationship type label matching ontology exactly (case-sensitive).",
    )
    parser.add_argument(
        "source_entity_type",
        help="Source entity type label matching ontology exactly (case-sensitive).",
    )
    parser.add_argument(
        "target_entity_type",
        help="Target entity type label matching ontology exactly (case-sensitive).",
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Path to JSON file; omit to read stdin.",
    )
    parser.add_argument(
        "--tenant-id", default="", help="Tenant id for deterministic ids."
    )
    parser.add_argument("--data-source-id", default="schema-bootstrap")
    args = parser.parse_args()

    raw = (
        Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
    )
    relationships = load_relationships(json.loads(raw))
    for row in relationships:
        line = relationship_to_create_line(
            relationship_label=args.relationship_label,
            source_entity_type=args.source_entity_type,
            target_entity_type=args.target_entity_type,
            source_slug=row["source_slug"],
            target_slug=row["target_slug"],
            properties=row["properties"],
            data_source_id=args.data_source_id,
            tenant_id=args.tenant_id,
        )
        sys.stdout.write(json.dumps(line, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
