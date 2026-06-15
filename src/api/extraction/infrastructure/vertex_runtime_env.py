"""Vertex AI environment helpers for Claude Agent SDK runtimes."""

from __future__ import annotations

import json
import os
from typing import Any

GCLOUD_ADC_FILENAME = "application_default_credentials.json"
DEFAULT_GCLOUD_CONTAINER_PATH = "/gcloud/config"
# OpenShell sandboxes cannot bind-mount host gcloud config; upload ADC under /tmp instead.
OPENSHELL_GCLOUD_CONTAINER_PATH = "/tmp/kartograph-gcloud"


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


def build_openshell_inference_container_env() -> dict[str, str]:
    """Route Claude Code through OpenShell inference.local (host holds Vertex ADC).

    Do not set ``CLAUDE_CODE_USE_VERTEX`` — that triggers metadata-server ADC
    inside the sandbox, which OpenShell blocks for SSRF hardening.
    """
    return {
        "ANTHROPIC_BASE_URL": "https://inference.local",
        "ANTHROPIC_API_KEY": "unused",
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
    }


def build_gcloud_adc_env(*, container_config_path: str) -> dict[str, str]:
    """Env vars so Google client libraries find ADC inside extraction containers."""
    base = container_config_path.rstrip("/")
    return {
        "CLOUDSDK_CONFIG": base,
        "GOOGLE_APPLICATION_CREDENTIALS": f"{base}/{GCLOUD_ADC_FILENAME}",
        "HOME": "/tmp",
    }


def build_gcloud_config_bind(
    *,
    host_mount: str,
    container_path: str = DEFAULT_GCLOUD_CONTAINER_PATH,
) -> str:
    return f"{host_mount.rstrip('/')}:{container_path.rstrip('/')}:ro,z"


def claude_model_configured() -> bool:
    """Return True when Vertex or direct Anthropic API credentials are configured."""
    if vertex_enabled_from_env():
        return bool(os.getenv("ANTHROPIC_VERTEX_PROJECT_ID", "").strip())
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
