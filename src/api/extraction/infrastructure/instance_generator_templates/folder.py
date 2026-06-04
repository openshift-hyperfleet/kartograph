#!/usr/bin/env python3
"""Generate folder instances from directory structure under repository-files."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _folder_instance(folder: Path, data_dir: Path, source_name: str, *, is_root: bool) -> dict:
    rel_path = folder.relative_to(data_dir)
    if is_root:
        slug = f"root-{source_name}"
    else:
        slug = f"folder-{str(rel_path).replace('/', '-').replace('_', '-').lower()}"
    child_folders = sum(
        1 for entry in folder.iterdir() if entry.is_dir() and not entry.name.startswith(".")
    )
    child_files = sum(
        1 for entry in folder.iterdir() if entry.is_file() and not entry.name.startswith(".")
    )
    return {
        "slug": slug,
        "properties": {
            "folder_path": str(rel_path),
            "data_source": source_name,
            "child_folder_count": child_folders,
            "child_file_count": child_files,
        },
    }


def generate_instances(data_dir: Path) -> list[dict]:
    instances: list[dict] = []
    for source_dir in sorted(data_dir.iterdir()):
        if not source_dir.is_dir() or source_dir.name.startswith("."):
            continue
        source_name = source_dir.name
        instances.append(_folder_instance(source_dir, data_dir, source_name, is_root=True))
        for subdir in sorted(source_dir.rglob("*")):
            if subdir.is_dir() and not any(part.startswith(".") for part in subdir.parts):
                instances.append(_folder_instance(subdir, data_dir, source_name, is_root=False))
    return instances


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(generate_instances(root), indent=2))
