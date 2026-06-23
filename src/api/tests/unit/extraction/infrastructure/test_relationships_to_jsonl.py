"""Unit tests for relationships_to_jsonl helper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "extraction/infrastructure/instance_generator_templates/relationships_to_jsonl.py"
)


def test_relationships_to_jsonl_emits_edge_create_lines(tmp_path: Path) -> None:
    input_path = tmp_path / "repository_defines_test_instances.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "source_slug": "service-b",
                    "target_slug": "service-a",
                    "properties": {"weight": 1},
                }
            ]
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "depends_on",
            "service",
            "service",
            "--input",
            str(input_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    line = json.loads(proc.stdout.strip())
    assert line["op"] == "CREATE"
    assert line["type"] == "edge"
    assert line["label"] == "depends_on"
    assert line["start_id"].startswith("service:")
    assert line["end_id"].startswith("service:")
