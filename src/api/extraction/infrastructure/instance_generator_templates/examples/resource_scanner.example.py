#!/usr/bin/env python3
"""Reference scanner for Resource entities (K8s/custom resources, config files).

Copy to ``instance_generators/Resource.py`` and adapt resource kinds / globs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scanner_common import dedupe_instances, generate_slug

_RESOURCE_GLOBS = (
    "**/*.yaml",
    "**/*.yml",
    "**/templates/**/*.yaml",
    "**/manifests/**/*.yaml",
)


def scan(repository_files: Path) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    files: list[Path] = []
    for data_source_dir in sorted(repository_files.iterdir()):
        if not data_source_dir.is_dir():
            continue
        for pattern in _RESOURCE_GLOBS:
            files.extend(sorted(data_source_dir.glob(pattern)))
    files = sorted({path for path in files if path.is_file()})
    print(f"Found {len(files)} resource file(s)...", file=sys.stderr)

    for index, file_path in enumerate(files):
        if index > 0 and index % 30 == 0:
            print(f"Progress: {index}/{len(files)}...", file=sys.stderr)
        data_source = file_path.relative_to(repository_files).parts[0]
        rel = file_path.relative_to(repository_files / data_source)
        slug = generate_slug(f"{data_source}-{rel.stem}")
        instances.append(
            {
                "slug": slug,
                "properties": {
                    "name": file_path.name,
                    "kind": "Resource",
                    "file_path": str(rel),
                    "data_source": data_source,
                    "description": f"Resource manifest: {rel}",
                },
            }
        )

    unique, skipped = dedupe_instances(instances)
    if skipped:
        print(f"Skipped {skipped} duplicate slug(s).", file=sys.stderr)
    print(f"Scan complete: {len(unique)} resource(s).", file=sys.stderr)
    return unique


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(scan(root), indent=2))
