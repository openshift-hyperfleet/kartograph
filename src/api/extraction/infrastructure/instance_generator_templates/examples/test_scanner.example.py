#!/usr/bin/env python3
"""Reference scanner for test-like entities (E2ETest, ComponentTest).

Copy to ``instance_generators/{Label}.py`` and adapt glob patterns / parsers.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from scanner_common import dedupe_instances, generate_slug

_E2E_SUITE_DIRS = ("adapter", "cluster", "nodepool", "channel", "version")
_GINKGO_IT = re.compile(
    r"^\s*(?:It|PIt|FIt)\(\s*[\"']([^\"']+)[\"']",
    re.MULTILINE,
)


def _suite_from_path(path: Path, repository_files: Path) -> str:
    rel_parts = path.relative_to(repository_files).parts
    for part in rel_parts:
        if part in _E2E_SUITE_DIRS:
            return part
    return "unknown"


def scan(repository_files: Path) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    patterns = ("**/e2e/**/*.go", "**/*_test.go", "**/test_*.py")
    files: list[Path] = []
    for data_source_dir in sorted(repository_files.iterdir()):
        if not data_source_dir.is_dir():
            continue
        for pattern in patterns:
            files.extend(sorted(data_source_dir.glob(pattern)))
    files = sorted({path for path in files if path.is_file()})
    print(f"Found {len(files)} test file(s)...", file=sys.stderr)

    for index, file_path in enumerate(files):
        if index > 0 and index % 20 == 0:
            print(f"Progress: {index}/{len(files)}...", file=sys.stderr)
        data_source = next(
            parent.name
            for parent in file_path.parents
            if parent.parent == repository_files
        )
        rel = file_path.relative_to(repository_files / data_source)
        content = file_path.read_text(encoding="utf-8", errors="replace")
        for match in _GINKGO_IT.finditer(content):
            title = match.group(1)
            slug = generate_slug(title)
            line_number = content.count("\n", 0, match.start()) + 1
            instances.append(
                {
                    "slug": slug,
                    "properties": {
                        "name": title,
                        "suite": _suite_from_path(file_path, repository_files),
                        "file_path": str(rel),
                        "line_number": line_number,
                        "labels": [],
                        "tier": "medium",
                        "description": f"Test: {title}",
                    },
                }
            )

    unique, skipped = dedupe_instances(instances)
    if skipped:
        print(f"Skipped {skipped} duplicate slug(s).", file=sys.stderr)
    print(f"Scan complete: {len(unique)} test instance(s).", file=sys.stderr)
    return unique


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("repository-files")
    print(json.dumps(scan(root), indent=2))
