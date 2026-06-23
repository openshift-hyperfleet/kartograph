#!/usr/bin/env python3
"""Reference scanner for APIEndpoint entities.

Looks for route registrations and OpenAPI-style path declarations.
Copy to ``instance_generators/APIEndpoint.py`` and customize patterns.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from scanner_common import dedupe_instances, generate_slug

_ROUTE_PATTERNS = (
    re.compile(r"@app\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']"),
    re.compile(r"router\.(Get|Post|Put|Patch|Delete)\(\s*[\"']([^\"']+)[\"']"),
    re.compile(r"HandleFunc\(\s*[\"']([^\"']+)[\"']"),
)


def scan(repository_files: Path) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    files = sorted(path for path in repository_files.rglob("*") if path.is_file())
    print(f"Scanning {len(files)} file(s) for API endpoints...", file=sys.stderr)

    for index, file_path in enumerate(files):
        if file_path.suffix not in {".go", ".py", ".ts", ".yaml", ".yml"}:
            continue
        if index > 0 and index % 40 == 0:
            print(f"Progress: {index}/{len(files)}...", file=sys.stderr)
        data_source = next(
            (
                parent.name
                for parent in file_path.parents
                if parent.parent == repository_files
            ),
            "unknown",
        )
        rel = file_path.relative_to(repository_files / data_source)
        content = file_path.read_text(encoding="utf-8", errors="replace")
        for pattern in _ROUTE_PATTERNS:
            for match in pattern.finditer(content):
                path_value = match.group(match.lastindex or 1)
                method = (
                    match.group(1).upper()
                    if match.lastindex and match.lastindex > 1
                    else "GET"
                )
                slug = generate_slug(f"{method}-{path_value}")
                instances.append(
                    {
                        "slug": slug,
                        "properties": {
                            "name": path_value,
                            "method": method,
                            "path": path_value,
                            "file_path": str(rel),
                            "description": f"{method} {path_value}",
                        },
                    }
                )

    unique, skipped = dedupe_instances(instances)
    if skipped:
        print(f"Skipped {skipped} duplicate slug(s).", file=sys.stderr)
    print(f"Scan complete: {len(unique)} endpoint(s).", file=sys.stderr)
    return unique


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(scan(root), indent=2))
