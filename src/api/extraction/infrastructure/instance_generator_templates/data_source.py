#!/usr/bin/env python3
"""Generate one entity instance per data-source folder under repository-files."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def generate_instances(data_dir: Path) -> list[dict]:
    instances: list[dict] = []
    for source_dir in sorted(data_dir.iterdir()):
        if not source_dir.is_dir() or source_dir.name.startswith("."):
            continue
        file_count = sum(1 for path in source_dir.rglob("*") if path.is_file())
        instances.append(
            {
                "slug": source_dir.name,
                "properties": {
                    "name": source_dir.name,
                    "source_type": "repository",
                    "file_count": file_count,
                },
            }
        )
    return instances


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(generate_instances(root), indent=2))
