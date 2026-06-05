#!/usr/bin/env python3
"""Reference scanner for Adapter entities.

Looks for adapter registration/config files. Copy to ``instance_generators/Adapter.py``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from scanner_common import dedupe_instances, generate_slug

_ADAPTER_NAME = re.compile(r"adapter[_-]?name[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE)


def scan(repository_files: Path) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    patterns = ("**/adapter/**/*.yaml", "**/adapters/**/*.yaml", "**/*adapter*.go")
    files: list[Path] = []
    for data_source_dir in sorted(repository_files.iterdir()):
        if not data_source_dir.is_dir():
            continue
        for pattern in patterns:
            files.extend(sorted(data_source_dir.glob(pattern)))
    files = sorted({path for path in files if path.is_file()})
    print(f"Found {len(files)} adapter candidate file(s)...", file=sys.stderr)

    for index, file_path in enumerate(files):
        if index > 0 and index % 20 == 0:
            print(f"Progress: {index}/{len(files)}...", file=sys.stderr)
        data_source = file_path.relative_to(repository_files).parts[0]
        rel = file_path.relative_to(repository_files / data_source)
        content = file_path.read_text(encoding="utf-8", errors="replace")
        names = [match.group(1) for match in _ADAPTER_NAME.finditer(content)]
        if not names:
            names = [file_path.stem]
        for name in names:
            slug = generate_slug(name)
            instances.append(
                {
                    "slug": slug,
                    "properties": {
                        "name": name,
                        "file_path": str(rel),
                        "data_source": data_source,
                        "description": f"Adapter: {name}",
                    },
                }
            )

    unique, skipped = dedupe_instances(instances)
    if skipped:
        print(f"Skipped {skipped} duplicate slug(s).", file=sys.stderr)
    print(f"Scan complete: {len(unique)} adapter(s).", file=sys.stderr)
    return unique


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(scan(root), indent=2))
