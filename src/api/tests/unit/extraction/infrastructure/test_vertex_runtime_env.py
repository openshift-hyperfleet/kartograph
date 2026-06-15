"""Tests for Vertex and OpenShell inference runtime env helpers."""

from __future__ import annotations

from extraction.infrastructure.vertex_runtime_env import (
    build_openshell_inference_container_env,
    build_vertex_container_env,
)


def test_build_openshell_inference_container_env_routes_through_inference_local() -> None:
    env = build_openshell_inference_container_env()
    assert env["ANTHROPIC_BASE_URL"] == "https://inference.local"
    assert env["ANTHROPIC_API_KEY"] == "unused"
    assert "CLAUDE_CODE_USE_VERTEX" not in env


def test_build_vertex_container_env_sets_vertex_flags() -> None:
    env = build_vertex_container_env(project_id="proj", region="us-east5")
    assert env["CLAUDE_CODE_USE_VERTEX"] == "1"
    assert env["ANTHROPIC_VERTEX_PROJECT_ID"] == "proj"
    assert env["CLOUD_ML_REGION"] == "us-east5"
