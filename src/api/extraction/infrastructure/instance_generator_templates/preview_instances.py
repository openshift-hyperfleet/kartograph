#!/usr/bin/env python3
"""Preview scanner JSON before converting to JSONL.

Example:

  python3 instance_generators/preview_instances.py E2ETest --limit 5
  python3 instance_generators/preview_instances.py E2ETest \\
    instance_generators/out/E2ETest_instances.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _default_input_path(entity_label: str) -> Path:
    return Path("instance_generators") / "out" / f"{entity_label}_instances.json"


def _format_row(index: int, row: dict[str, Any]) -> str:
    slug = str(row.get("slug") or "?")
    properties = row.get("properties") or {}
    if not isinstance(properties, dict):
        properties = {}
    lines = [f"{index}. {slug}"]
    for key in sorted(properties):
        lines.append(f"   - {key}: {properties[key]!r}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview entity scanner JSON output.")
    parser.add_argument("entity_label", help="Entity type label (matches scanner filename).")
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to JSON file (default: instance_generators/out/{label}_instances.json).",
    )
    parser.add_argument("--limit", type=int, default=5, help="Max instances to print.")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else _default_input_path(args.entity_label)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Scanner output must be a JSON array")

    total = len(payload)
    limit = max(1, args.limit)
    preview = payload[:limit]
    print(f"Preview of {args.entity_label} instances ({len(preview)} of {total}):\n")
    for index, row in enumerate(preview, start=1):
        if isinstance(row, dict):
            print(_format_row(index, row))
            print()
    if total > limit:
        print(f"... and {total - limit} more. Run entities_to_jsonl.py when ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
