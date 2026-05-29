"""Unit tests for Vertex runtime environment helpers."""

from __future__ import annotations

import pytest

from extraction.infrastructure.vertex_runtime_env import (
    build_vertex_container_env,
    vertex_enabled_from_env,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("0", False),
        ("", False),
        (None, False),
    ],
)
def test_vertex_enabled_from_env(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool
) -> None:
    if value is None:
        monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", value)
    assert vertex_enabled_from_env() is expected


def test_build_vertex_container_env_includes_project_and_region() -> None:
    env = build_vertex_container_env(
        project_id="my-gcp-project",
        region="us-central1",
    )
    assert env["CLAUDE_CODE_USE_VERTEX"] == "1"
    assert env["ANTHROPIC_VERTEX_PROJECT_ID"] == "my-gcp-project"
    assert env["CLOUD_ML_REGION"] == "us-central1"
    assert env["VERTEXAI_LOCATION"] == "us-central1"
