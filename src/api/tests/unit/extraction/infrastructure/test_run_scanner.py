"""Unit tests for the run_scanner prepopulation pipeline wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RUN_SCANNER = (
    Path(__file__).resolve().parents[4]
    / "extraction/infrastructure/instance_generator_templates/run_scanner.py"
)
ENTITIES_TO_JSONL = RUN_SCANNER.parent / "entities_to_jsonl.py"
RELATIONSHIPS_TO_JSONL = RUN_SCANNER.parent / "relationships_to_jsonl.py"
SCANNER_COMMON = RUN_SCANNER.parent / "scanner_common.py"


def _write_entity_scanner(generators_dir: Path, label: str) -> None:
    (generators_dir / f"{label}.py").write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "def main():",
                "    print(json.dumps([",
                '        {"slug": "alpha", "properties": {"name": "Alpha"}},',
                '        {"slug": "beta", "properties": {"name": "Beta"}},',
                "    ]))",
                'if __name__ == "__main__":',
                "    main()",
            ]
        ),
        encoding="utf-8",
    )


def _write_relationship_scanner(generators_dir: Path, stem: str) -> None:
    (generators_dir / f"{stem}.py").write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "def main():",
                "    print(json.dumps([",
                '        {"source_slug": "alpha", "target_slug": "beta", "properties": {}},',
                "    ]))",
                'if __name__ == "__main__":',
                "    main()",
            ]
        ),
        encoding="utf-8",
    )


def _bootstrap_workspace(tmp_path: Path) -> Path:
    generators_dir = tmp_path / "instance_generators"
    generators_dir.mkdir()
    (generators_dir / "out").mkdir()
    for script in (ENTITIES_TO_JSONL, RELATIONSHIPS_TO_JSONL, SCANNER_COMMON):
        (generators_dir / script.name).write_text(
            script.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (generators_dir / "run_scanner.py").write_text(
        RUN_SCANNER.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "repository-files").mkdir()
    return tmp_path


def test_run_scanner_entity_pipeline(tmp_path: Path) -> None:
    workspace = _bootstrap_workspace(tmp_path)
    _write_entity_scanner(workspace / "instance_generators", "Resource")

    proc = subprocess.run(
        [
            sys.executable,
            str(workspace / "instance_generators" / "run_scanner.py"),
            "Resource",
            "--entity",
            "--repository-files",
            str(workspace / "repository-files"),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=workspace,
    )

    summary = json.loads(proc.stdout)
    assert summary["kind"] == "entity"
    assert summary["instance_count"] == 2
    assert summary["jsonl_line_count"] == 2
    assert summary["jsonl_path"].endswith("Resource_instances.jsonl")
    assert "apply_graph_mutations_from_file" in summary["next_step"]

    jsonl_path = workspace / summary["jsonl_path"]
    assert jsonl_path.is_file()
    lines = [
        line
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2
    assert json.loads(lines[0])["label"] == "Resource"


def test_run_scanner_relationship_pipeline(tmp_path: Path) -> None:
    workspace = _bootstrap_workspace(tmp_path)
    stem = "ComponentTest_tests_APIEndpoint"
    _write_relationship_scanner(workspace / "instance_generators", stem)

    proc = subprocess.run(
        [
            sys.executable,
            str(workspace / "instance_generators" / "run_scanner.py"),
            "--relationship",
            "--source",
            "ComponentTest",
            "--rel",
            "tests",
            "--target",
            "APIEndpoint",
            "--repository-files",
            str(workspace / "repository-files"),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=workspace,
    )

    summary = json.loads(proc.stdout)
    assert summary["kind"] == "relationship"
    assert summary["jsonl_path"].endswith(f"{stem}_instances.jsonl")
    assert (workspace / summary["jsonl_path"]).is_file()


def test_run_scanner_validate_only(tmp_path: Path) -> None:
    workspace = _bootstrap_workspace(tmp_path)
    _write_entity_scanner(workspace / "instance_generators", "Adapter")

    proc = subprocess.run(
        [
            sys.executable,
            str(workspace / "instance_generators" / "run_scanner.py"),
            "Adapter",
            "--entity",
            "--validate-only",
            "--repository-files",
            str(workspace / "repository-files"),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=workspace,
    )

    summary = json.loads(proc.stdout)
    assert "validate_graph_mutations_from_file" in summary["next_step"]
    assert "apply_graph_mutations_from_file" not in summary["next_step"]
