"""Vertex AI helpers for Claude Agent SDK in sticky session containers."""

from __future__ import annotations

import os
from typing import Literal

VertexEffortLevel = Literal["low", "medium", "high", "max"]

# Vertex AI (direct or via OpenShell inference.local) rejects xhigh effort levels.
VERTEX_COMPATIBLE_EFFORT: VertexEffortLevel = "high"


def is_truthy_env(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def vertex_enabled_from_env() -> bool:
    return is_truthy_env(os.getenv("CLAUDE_CODE_USE_VERTEX"))


def build_claude_agent_env(settings) -> dict[str, str]:
    """Build Claude Agent SDK env for Vertex, OpenShell inference.local, or Anthropic API."""
    env: dict[str, str] = {}
    if getattr(settings, "openshell_inference_enabled", lambda: False)():
        env["ANTHROPIC_BASE_URL"] = "https://inference.local"
        env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key.strip() or "unused"
        env["CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"] = "1"
        return env
    if settings.vertex_enabled():
        env["CLAUDE_CODE_USE_VERTEX"] = "1"
        if settings.vertex_project_id.strip():
            env["ANTHROPIC_VERTEX_PROJECT_ID"] = settings.vertex_project_id.strip()
        region = settings.vertex_region.strip()
        if region:
            env["CLOUD_ML_REGION"] = region
            env["VERTEXAI_LOCATION"] = region
        return env
    if settings.anthropic_api_key.strip():
        env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key.strip()
    return env
