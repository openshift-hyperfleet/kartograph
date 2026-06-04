#!/usr/bin/env python3
"""Generate one entity instance per source file under repository-files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

FILE_EXTENSIONS = (
    ".md",
    ".go",
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".ts",
    ".tsx",
    ".js",
    ".java",
    ".rs",
    ".rb",
    ".sh",
)


def _path_to_slug(rel_path: Path) -> str:
    return str(rel_path).replace("/", "-").replace("_", "-").replace(".", "-").lower()


def generate_instances(data_dir: Path) -> list[dict]:
    instances: list[dict] = []
    for source_dir in sorted(data_dir.iterdir()):
        if not source_dir.is_dir() or source_dir.name.startswith("."):
            continue
        for file_path in sorted(source_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in FILE_EXTENSIONS:
                continue
            if any(part.startswith(".") for part in file_path.parts):
                continue
            rel_path = file_path.relative_to(data_dir)
            instances.append(
                {
                    "slug": _path_to_slug(rel_path),
                    "properties": {
                        "file_path": str(rel_path),
                        "name": file_path.name,
                        "source_path": str(rel_path),
                    },
                }
            )
    return instances


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(generate_instances(root), indent=2))
