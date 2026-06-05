#!/usr/bin/env python3
"""Example entity scanner — copy to ``{entity_label}.py`` and customize discovery logic.

Contract:
- argv[1]: path to ``repository-files/`` (one folder per data source)
- stdout: JSON array of ``{"slug": "...", "properties": {...}}`` sorted deterministically
- stderr: optional progress logging only

Output file convention: ``instance_generators/out/{entity_label}_instances.json``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def scan(repository_files: Path) -> list[dict]:
    """Find every instance of this entity type across all data sources."""
    instances: list[dict] = []
    for data_source_dir in sorted(repository_files.iterdir()):
        if not data_source_dir.is_dir() or data_source_dir.name.startswith("."):
            continue
        # Example: one instance per *_test.go file — replace with your entity's discovery rules.
        for file_path in sorted(data_source_dir.rglob("*_test.go")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(data_source_dir)
            slug = f"{data_source_dir.name}-{str(rel).replace('/', '-').replace('_', '-')}".lower()
            instances.append(
                {
                    "slug": slug,
                    "properties": {
                        "name": file_path.name,
                        "file_path": str(rel),
                        "data_source": data_source_dir.name,
                    },
                }
            )
    return sorted(instances, key=lambda row: row["slug"])


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(scan(root), indent=2))
