#!/usr/bin/env python3
"""Example relationship scanner — copy to ``{source}_{rel}_{target}.py``.

NAMING CONVENTION: Filename uses source entity label, relationship label, and target
entity label from the ontology (case-sensitive), e.g. ``ComponentTest_exercises_APIEndpoint.py``.

Contract:
- argv[1]: path to ``repository-files/`` (one folder per data source)
- stdout: JSON array of ``{"source_slug": "...", "target_slug": "...", "properties": {...}}``
- stderr: progress logging only

Output file convention:
``instance_generators/out/{source}_{rel}_{target}_instances.json``

Prerequisites:
- Entity prepopulation finished for both endpoint types (slugs must exist in the graph).
- Use ``kartograph_list_instances_by_type`` or ``kartograph_check_graph_slugs`` when matching.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scanner_common import dedupe_relationships, generate_slug


def scan(repository_files: Path) -> list[dict[str, Any]]:
    """Discover relationship instances across all data sources."""
    relationships: list[dict[str, Any]] = []
    files = sorted(path for path in repository_files.rglob("*") if path.is_file())
    print(f"Scanning {len(files)} files for relationships...", file=sys.stderr)

    for index, file_path in enumerate(files):
        if index > 0 and index % 50 == 0:
            print(f"Progress: {index}/{len(files)} files...", file=sys.stderr)
        # Replace with logic that maps repository evidence to known entity slugs.
        source_slug = generate_slug(file_path.stem)
        target_slug = generate_slug(f"{file_path.parent.name}-target")
        relationships.append(
            {
                "source_slug": source_slug,
                "target_slug": target_slug,
                "properties": {
                    "source_path": str(file_path.relative_to(repository_files)),
                },
            }
        )

    unique, skipped = dedupe_relationships(relationships)
    if skipped:
        print(f"Skipped {skipped} duplicate relationship row(s).", file=sys.stderr)
    print(f"Scan complete: {len(unique)} relationship(s).", file=sys.stderr)
    return unique


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(scan(root), indent=2))
