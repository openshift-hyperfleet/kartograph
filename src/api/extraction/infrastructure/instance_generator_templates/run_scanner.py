#!/usr/bin/env python3
"""Run a prepopulation scanner and convert output to JSONL in one step.

Entity example:

  python3 instance_generators/run_scanner.py Resource --entity

Relationship example:

  python3 instance_generators/run_scanner.py \\
    --relationship --source ComponentTest --rel tests --target APIEndpoint

Then call ``kartograph_validate_graph_mutations_from_file`` (optional dry run) and
``kartograph_apply_graph_mutations_from_file`` with the printed ``jsonl_path``.
Apply pre-validates internally; separate validate is optional.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scanner_common import relationship_output_paths, relationship_scanner_stem

GENERATORS_DIR = Path(__file__).resolve().parent
OUT_DIR = GENERATORS_DIR / "out"


def _entity_paths(label: str) -> tuple[Path, Path, Path]:
    scanner = GENERATORS_DIR / f"{label}.py"
    json_path = OUT_DIR / f"{label}_instances.json"
    jsonl_path = OUT_DIR / f"{label}_instances.jsonl"
    return scanner, json_path, jsonl_path


def _relationship_paths(*, source: str, relationship: str, target: str) -> tuple[Path, Path, Path]:
    stem = relationship_scanner_stem(
        source=source,
        relationship=relationship,
        target=target,
    )
    json_rel, jsonl_rel = relationship_output_paths(
        source=source,
        relationship=relationship,
        target=target,
    )
    return GENERATORS_DIR / f"{stem}.py", Path(json_rel), Path(jsonl_rel)


def _run_scanner(*, scanner_path: Path, repository_files: Path, json_path: Path) -> None:
    if not scanner_path.is_file():
        raise FileNotFoundError(f"Scanner not found: {scanner_path}")
    if not repository_files.is_dir():
        raise FileNotFoundError(f"Repository files directory not found: {repository_files}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        subprocess.run(
            [sys.executable, str(scanner_path), str(repository_files)],
            check=True,
            stdout=handle,
        )


def _convert_entity_jsonl(
    *,
    label: str,
    json_path: Path,
    jsonl_path: Path,
    data_source_id: str,
) -> int:
    with jsonl_path.open("w", encoding="utf-8") as handle:
        subprocess.run(
            [
                sys.executable,
                str(GENERATORS_DIR / "entities_to_jsonl.py"),
                label,
                "--data-source-id",
                data_source_id,
                str(json_path),
            ],
            check=True,
            stdout=handle,
        )
    return sum(1 for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip())


def _convert_relationship_jsonl(
    *,
    source: str,
    relationship: str,
    target: str,
    json_path: Path,
    jsonl_path: Path,
    data_source_id: str,
) -> int:
    with jsonl_path.open("w", encoding="utf-8") as handle:
        subprocess.run(
            [
                sys.executable,
                str(GENERATORS_DIR / "relationships_to_jsonl.py"),
                relationship,
                source,
                target,
                "--data-source-id",
                data_source_id,
                str(json_path),
            ],
            check=True,
            stdout=handle,
        )
    return sum(1 for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip())


def _load_instance_count(json_path: Path) -> int:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Scanner output must be a JSON array")
    return len(payload)


def _emit_summary(summary: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a prepopulation scanner and convert output to JSONL.",
    )
    parser.add_argument(
        "label",
        nargs="?",
        help="Entity type label when using --entity.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--entity", action="store_true", help="Run an entity scanner.")
    mode.add_argument("--relationship", action="store_true", help="Run a relationship scanner.")
    parser.add_argument("--source", help="Relationship source entity type label.")
    parser.add_argument("--rel", help="Relationship type label.")
    parser.add_argument("--target", help="Relationship target entity type label.")
    parser.add_argument(
        "--repository-files",
        default="repository-files",
        help="Directory passed to the scanner (default: repository-files).",
    )
    parser.add_argument(
        "--data-source-id",
        default="schema-bootstrap",
        help="data_source_id written into JSONL rows.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Stop after JSONL conversion; do not suggest apply.",
    )
    args = parser.parse_args()

    repository_files = Path(args.repository_files)
    if args.entity:
        if not args.label:
            parser.error("entity label is required when using --entity")
        scanner_path, json_path, jsonl_path = _entity_paths(args.label)
        _run_scanner(
            scanner_path=scanner_path,
            repository_files=repository_files,
            json_path=json_path,
        )
        instance_count = _load_instance_count(json_path)
        jsonl_lines = _convert_entity_jsonl(
            label=args.label,
            json_path=json_path,
            jsonl_path=jsonl_path,
            data_source_id=args.data_source_id,
        )
        summary: dict[str, Any] = {
            "kind": "entity",
            "label": args.label,
            "scanner_path": str(scanner_path),
            "json_path": str(json_path),
            "jsonl_path": str(jsonl_path),
            "instance_count": instance_count,
            "jsonl_line_count": jsonl_lines,
        }
    else:
        if not args.source or not args.rel or not args.target:
            parser.error("--relationship requires --source, --rel, and --target")
        scanner_path, json_path, jsonl_path = _relationship_paths(
            source=args.source,
            relationship=args.rel,
            target=args.target,
        )
        _run_scanner(
            scanner_path=scanner_path,
            repository_files=repository_files,
            json_path=json_path,
        )
        instance_count = _load_instance_count(json_path)
        jsonl_lines = _convert_relationship_jsonl(
            source=args.source,
            relationship=args.rel,
            target=args.target,
            json_path=json_path,
            jsonl_path=jsonl_path,
            data_source_id=args.data_source_id,
        )
        summary = {
            "kind": "relationship",
            "source_entity_type": args.source,
            "relationship_type": args.rel,
            "target_entity_type": args.target,
            "scanner_path": str(scanner_path),
            "json_path": str(json_path),
            "jsonl_path": str(jsonl_path),
            "instance_count": instance_count,
            "jsonl_line_count": jsonl_lines,
        }

    if args.validate_only:
        summary["next_step"] = (
            f"kartograph_validate_graph_mutations_from_file path={summary['jsonl_path']}"
        )
    else:
        summary["next_step"] = (
            f"kartograph_apply_graph_mutations_from_file path={summary['jsonl_path']} "
            "(apply pre-validates; optional validate first for dry run)"
        )
    _emit_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
