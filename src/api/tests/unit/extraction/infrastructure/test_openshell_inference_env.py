"""Unit tests for OpenShell inference.local sandbox env."""

from __future__ import annotations

from extraction.infrastructure.openshell.inference_env import (
    build_openshell_inference_env_script_lines,
    insert_claude_bare_flag,
    insert_vertex_compatible_effort,
)


def test_inference_env_script_uses_inference_local_not_vertex_adc() -> None:
    lines = build_openshell_inference_env_script_lines()

    joined = "\n".join(lines)
    assert "ANTHROPIC_BASE_URL=https://inference.local" in joined
    assert "ANTHROPIC_API_KEY=unused" in joined
    assert "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1" in joined
    assert "KARTOGRAPH_WORKSPACE=/sandbox" in joined
    assert "CLAUDE_CODE_USE_VERTEX" not in joined


def test_insert_claude_bare_flag_adds_bare_after_binary() -> None:
    args = insert_claude_bare_flag(["claude", "--model", "claude-opus-4-6", "-p", "hi"])

    assert args[:3] == ["claude", "--bare", "--model"]


def test_insert_claude_bare_flag_is_idempotent() -> None:
    args = ["claude", "--bare", "-p", "hi"]

    assert insert_claude_bare_flag(args) == args


def test_insert_vertex_compatible_effort_adds_high_after_bare() -> None:
    args = insert_vertex_compatible_effort(
        insert_claude_bare_flag(["claude", "--model", "claude-opus-4-6", "-p", "hi"]),
    )

    assert args[:5] == ["claude", "--bare", "--effort", "high", "--model"]
