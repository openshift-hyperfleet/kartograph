#!/usr/bin/env python3
"""Example entity scanner — copy to ``{entity_label}.py`` and customize discovery logic.

NAMING CONVENTION: The filename MUST match the ontology entity type ``label`` exactly
(case-sensitive). Examples: ``E2ETest.py``, ``APIEndpoint.py``, ``ComponentTest.py``.
Do not use lowercase variants like ``e2etest.py``.

Contract:
- argv[1]: path to ``repository-files/`` (one folder per data source)
- stdout: JSON array of ``{"slug": "...", "properties": {...}}`` sorted deterministically
- stderr: progress logging only

Output file convention: ``instance_generators/out/{entity_label}_instances.json``

See ``PREPOPULATION_WORKFLOW.md`` for the full six-step pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scanner_common import dedupe_instances, generate_slug


def scan(repository_files: Path) -> list[dict]:
    """Find every instance of this entity type across all data sources."""
    instances: list[dict[str, Any]] = []
    files = sorted(
        path for path in repository_files.rglob("*_test.go") if path.is_file()
    )
    print(f"Found {len(files)} candidate file(s)...", file=sys.stderr)

    for index, file_path in enumerate(files):
        if index > 0 and index % 25 == 0:
            print(f"Progress: {index}/{len(files)} files scanned...", file=sys.stderr)
        data_source_dir = next(
            (
                parent
                for parent in file_path.parents
                if parent.parent == repository_files
            ),
            repository_files,
        )
        rel = file_path.relative_to(data_source_dir)
        slug = generate_slug(f"{data_source_dir.name}-{rel.stem}")
        instances.append(
            {
                "slug": slug,
                "properties": {
                    "name": file_path.stem,
                    "file_path": str(rel),
                    "data_source": data_source_dir.name,
                    "description": f"Example instance from {rel}",
                },
            }
        )

    unique, skipped = dedupe_instances(instances)
    if skipped:
        print(f"Skipped {skipped} duplicate slug(s).", file=sys.stderr)
    print(f"Scan complete: {len(unique)} instance(s).", file=sys.stderr)
    return unique


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(scan(root), indent=2))
