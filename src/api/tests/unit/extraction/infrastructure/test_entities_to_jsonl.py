"""Unit tests for the entities_to_jsonl helper script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "extraction/infrastructure/instance_generator_templates/entities_to_jsonl.py"
)


def test_entities_to_jsonl_emits_sorted_create_lines(tmp_path: Path) -> None:
    instances_path = tmp_path / "test_instances.json"
    instances_path.write_text(
        json.dumps(
            [
                {"slug": "b-entity", "properties": {"name": "B"}},
                {"slug": "a-entity", "properties": {"name": "A", "file_path": "pkg/a.go"}},
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "test",
            "--data-source-id",
            "schema-bootstrap",
            str(instances_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["set_properties"]["slug"] == "a-entity"
    assert second["set_properties"]["slug"] == "b-entity"
    assert first["label"] == "test"
    assert first["set_properties"]["data_source_id"] == "schema-bootstrap"

    rerun = subprocess.run(
        [sys.executable, str(SCRIPT), "test", str(instances_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert rerun.stdout == proc.stdout


def test_entities_to_jsonl_omits_source_path_when_not_configured(tmp_path: Path) -> None:
    instances_path = tmp_path / "test_instances.json"
    instances_path.write_text(
        json.dumps([{"slug": "a-entity", "properties": {"name": "A"}}]),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "test", str(instances_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    line = json.loads(proc.stdout.strip())
    assert "source_path" not in line["set_properties"]


def test_entities_to_jsonl_preserves_source_path_from_scanner_properties(tmp_path: Path) -> None:
    instances_path = tmp_path / "test_instances.json"
    instances_path.write_text(
        json.dumps(
            [{"slug": "a-entity", "properties": {"name": "A", "source_path": "pkg/a_test.go"}}]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "test", str(instances_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    line = json.loads(proc.stdout.strip())
    assert line["set_properties"]["source_path"] == "pkg/a_test.go"
