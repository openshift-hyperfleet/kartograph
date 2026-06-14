#!/usr/bin/env python3
"""Diff current graph instances against a desired set and emit mutation JSONL.

Typical bulk cleanup workflow:

  1. Paginate ``kartograph_list_instances_by_type`` and save merged output to
     ``helpers/current_<Label>.json`` (object with ``nodes`` array).
  2. Save desired slugs or scanner output to ``helpers/desired_<Label>.json``.
  3. Generate JSONL::

       python3 helpers/sync_instances.py --entity-type Adapter \\
         --current helpers/current_Adapter.json \\
         --desired helpers/desired_Adapter.json \\
         --filter-data-source-id hyperfleet-e2e \\
         --out helpers/bulk_sync_Adapter.jsonl

  4. ``kartograph_validate_graph_mutations_from_file`` → ``apply-from-file`` once.

Use ``--create-missing`` with ``--data-source-id`` to emit CREATE lines for desired
slugs that are not already present in the current snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def parse_current_nodes(payload: Any) -> list[dict[str, Any]]:
    """Accept a list API response, a ``nodes`` array, or a bare node list."""
    if isinstance(payload, dict):
        nodes = payload.get("nodes")
        if isinstance(nodes, list):
            return [_normalize_current_node(node, index) for index, node in enumerate(nodes)]
        raise ValueError("Current snapshot object must include a nodes array")
    if isinstance(payload, list):
        return [_normalize_current_node(node, index) for index, node in enumerate(payload)]
    raise ValueError("Current snapshot must be a JSON object or array")


def _normalize_current_node(node: Any, index: int) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValueError(f"Current node at index {index} must be an object")
    node_id = node.get("id")
    slug = node.get("slug")
    if not node_id or not str(node_id).strip():
        raise ValueError(f"Current node at index {index} is missing id")
    if not slug or not str(slug).strip():
        raise ValueError(f"Current node at index {index} is missing slug")
    properties = node.get("properties") or {}
    if not isinstance(properties, dict):
        raise ValueError(f"Current node at index {index} properties must be an object")
    return {
        "id": str(node_id).strip(),
        "slug": str(slug).strip(),
        "properties": properties,
    }


def parse_desired_instances(payload: Any) -> dict[str, dict[str, Any]]:
    """Return slug → {properties} for desired instances."""
    if isinstance(payload, list):
        desired: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(payload):
            if isinstance(row, str):
                slug = row.strip()
                if not slug:
                    raise ValueError(f"Desired slug at index {index} must not be empty")
                desired[slug] = {"properties": {}}
                continue
            if not isinstance(row, dict):
                raise ValueError(f"Desired entry at index {index} must be a slug string or object")
            slug = row.get("slug")
            if not slug or not str(slug).strip():
                raise ValueError(f"Desired entry at index {index} is missing slug")
            properties = row.get("properties") or {}
            if not isinstance(properties, dict):
                raise ValueError(f"Desired entry at index {index} properties must be an object")
            desired[str(slug).strip()] = {"properties": dict(properties)}
        return desired
    raise ValueError("Desired snapshot must be a JSON array")


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
        "label": entity_label.strip(),
        "set_properties": set_properties,
    }


def build_sync_mutations(
    *,
    entity_type: str,
    current_nodes: list[dict[str, Any]],
    desired_by_slug: dict[str, dict[str, Any]],
    filter_data_source_id: str | None = None,
    create_missing: bool = False,
    data_source_id: str = "",
    tenant_id: str = "",
) -> list[dict[str, Any]]:
    """Return DELETE (and optional CREATE) mutation lines for one entity type."""
    entity_type = entity_type.strip()
    if not entity_type:
        raise ValueError("entity_type must not be empty")

    desired_slugs = set(desired_by_slug)
    current_slugs = {node["slug"] for node in current_nodes}
    lines: list[dict[str, Any]] = []

    for node in sorted(current_nodes, key=lambda item: item["slug"]):
        if filter_data_source_id:
            node_ds = str(node["properties"].get("data_source_id") or "").strip()
            if node_ds != filter_data_source_id.strip():
                continue
        if node["slug"] not in desired_slugs:
            lines.append({"op": "DELETE", "type": "node", "id": node["id"]})

    if create_missing:
        if not data_source_id.strip():
            raise ValueError("--data-source-id is required when --create-missing is set")
        for slug in sorted(desired_slugs - current_slugs):
            desired = desired_by_slug[slug]
            lines.append(
                instance_to_create_line(
                    entity_label=entity_type,
                    slug=slug,
                    properties=desired["properties"],
                    data_source_id=data_source_id.strip(),
                    tenant_id=tenant_id,
                )
            )

    return lines


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diff current graph instances against desired slugs and emit mutation JSONL.",
    )
    parser.add_argument(
        "--entity-type",
        required=True,
        help="Entity type label matching ontology exactly (case-sensitive).",
    )
    parser.add_argument(
        "--current",
        required=True,
        help="Path to JSON snapshot from kartograph_list_instances_by_type (nodes array).",
    )
    parser.add_argument(
        "--desired",
        required=True,
        help="Path to JSON array of desired slugs or scanner instances.",
    )
    parser.add_argument(
        "--out",
        help="Write JSONL to this path; omit to write stdout.",
    )
    parser.add_argument(
        "--filter-data-source-id",
        help="Only DELETE current nodes with this data_source_id property.",
    )
    parser.add_argument(
        "--create-missing",
        action="store_true",
        help="Emit CREATE lines for desired slugs absent from the current snapshot.",
    )
    parser.add_argument(
        "--data-source-id",
        default="",
        help="data_source_id for CREATE lines when --create-missing is set.",
    )
    parser.add_argument("--tenant-id", default="", help="Tenant id for deterministic CREATE ids.")
    args = parser.parse_args(argv)

    current_nodes = parse_current_nodes(_load_json(Path(args.current)))
    desired_by_slug = parse_desired_instances(_load_json(Path(args.desired)))
    lines = build_sync_mutations(
        entity_type=args.entity_type,
        current_nodes=current_nodes,
        desired_by_slug=desired_by_slug,
        filter_data_source_id=args.filter_data_source_id,
        create_missing=args.create_missing,
        data_source_id=args.data_source_id,
        tenant_id=args.tenant_id,
    )

    rendered = "".join(json.dumps(line, separators=(",", ":")) + "\n" for line in lines)
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
