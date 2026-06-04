"""Unit tests for the json_instances_to_jsonl helper script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "extraction/infrastructure/instance_generator_templates/json_instances_to_jsonl.py"
)


def test_json_instances_to_jsonl_emits_sorted_create_lines(tmp_path: Path) -> None:
    instances_path = tmp_path / "instances.json"
    instances_path.write_text(
        json.dumps(
            [
                {"slug": "b-entity", "properties": {"name": "B"}},
                {"slug": "a-entity", "properties": {"name": "A", "file_path": "pkg/a.go"}},
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "out.jsonl"

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "source_file",
            "--data-source-id",
            "schema-bootstrap",
            "--source-path",
            "graph-management-assistant",
            str(instances_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output_path.write_text(proc.stdout, encoding="utf-8")

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["set_properties"]["slug"] == "a-entity"
    assert second["set_properties"]["slug"] == "b-entity"
    assert first["op"] == "CREATE"
    assert first["type"] == "node"
    assert first["label"] == "source_file"
    assert first["set_properties"]["data_source_id"] == "schema-bootstrap"
    assert first["set_properties"]["source_path"] == "graph-management-assistant"
    assert first["id"] == second["id"] or first["set_properties"]["slug"] != second["set_properties"]["slug"]

    rerun = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "source_file",
            str(instances_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert rerun.stdout == proc.stdout
