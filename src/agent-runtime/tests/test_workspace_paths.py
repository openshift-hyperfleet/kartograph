"""Unit tests for workspace path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from kartograph_agent_runtime.workspace_paths import read_workspace_text_file, resolve_workspace_file


def test_resolve_workspace_file_rejects_path_traversal(tmp_path: Path) -> None:
    (tmp_path / "safe.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="within workspace"):
        resolve_workspace_file(str(tmp_path), "../outside.jsonl")


def test_read_workspace_text_file_reads_relative_path(tmp_path: Path) -> None:
    (tmp_path / "batch.jsonl").write_text('{"op":"CREATE"}\n', encoding="utf-8")
    content = read_workspace_text_file(str(tmp_path), "batch.jsonl")
    assert "CREATE" in content
