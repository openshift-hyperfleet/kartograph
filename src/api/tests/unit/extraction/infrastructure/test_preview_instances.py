"""Unit tests for preview_instances helper script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "extraction/infrastructure/instance_generator_templates/preview_instances.py"
)


def test_preview_instances_prints_limited_rows(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "E2ETest_instances.json"
    input_path.write_text(
        json.dumps(
            [
                {"slug": "alpha", "properties": {"suite": "adapter"}},
                {"slug": "beta", "properties": {"suite": "cluster"}},
                {"slug": "gamma", "properties": {"suite": "channel"}},
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "E2ETest", str(input_path), "--limit", "2"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Preview of E2ETest instances (2 of 3)" in proc.stdout
    assert "alpha" in proc.stdout
    assert "beta" in proc.stdout
    assert "gamma" not in proc.stdout
    assert "... and 1 more" in proc.stdout
