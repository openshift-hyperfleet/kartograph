"""Tests for Claude Agent SDK env construction."""

from __future__ import annotations

from kartograph_agent_runtime.settings import AgentRuntimeSettings
from kartograph_agent_runtime.vertex import VERTEX_COMPATIBLE_EFFORT, build_claude_agent_env


def test_build_claude_agent_env_uses_openshell_inference_without_vertex_adc() -> None:
    settings = AgentRuntimeSettings(
        ANTHROPIC_BASE_URL="https://inference.local",
        ANTHROPIC_API_KEY="unused",
        CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS="1",
    )
    env = build_claude_agent_env(settings)
    assert env["ANTHROPIC_BASE_URL"] == "https://inference.local"
    assert env["ANTHROPIC_API_KEY"] == "unused"
    assert "CLAUDE_CODE_USE_VERTEX" not in env


def test_openshell_inference_settings_count_as_model_configured() -> None:
    settings = AgentRuntimeSettings(ANTHROPIC_BASE_URL="https://inference.local")
    assert settings.openshell_inference_enabled() is True
    assert settings.model_configured() is True


def test_vertex_compatible_effort_avoids_xhigh() -> None:
    assert VERTEX_COMPATIBLE_EFFORT == "high"
