"""Vertex AI environment helpers for Claude Agent SDK runtimes."""

from __future__ import annotations

import os


def is_truthy_env(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def vertex_enabled_from_env() -> bool:
    return is_truthy_env(os.getenv("CLAUDE_CODE_USE_VERTEX"))


def build_vertex_container_env(
    *,
    project_id: str,
    region: str,
) -> dict[str, str]:
    """Return env vars for Claude Agent SDK Vertex mode inside sticky containers."""
    env: dict[str, str] = {"CLAUDE_CODE_USE_VERTEX": "1"}
    if project_id.strip():
        env["ANTHROPIC_VERTEX_PROJECT_ID"] = project_id.strip()
    if region.strip():
        env["CLOUD_ML_REGION"] = region.strip()
        env["VERTEXAI_LOCATION"] = region.strip()
    return env


def claude_model_configured() -> bool:
    """Return True when Vertex or direct Anthropic API credentials are configured."""
    if vertex_enabled_from_env():
        return bool(os.getenv("ANTHROPIC_VERTEX_PROJECT_ID", "").strip())
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
