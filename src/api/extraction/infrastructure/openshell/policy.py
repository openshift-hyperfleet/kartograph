"""OpenShell network policy resolution for GMA and extraction workloads."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml

from extraction.domain.value_objects import GraphManagementUiMode

PolicyEnforcement = Literal["soft", "hard_requirement"]

_BUNDLED_POLICY_DIR = Path(__file__).resolve().parent / "policies"

_DEFAULT_API_ENDPOINT = "api:8000:read-write"
_DEFAULT_INFERENCE_ENDPOINT = "inference.local:443:read-write"

_MODE_POLICY_FILES: dict[str, str] = {
    GraphManagementUiMode.INITIAL_SCHEMA_DESIGN.value: "gma-initial-schema-design.yaml",
    GraphManagementUiMode.EXTRACTION_JOBS.value: "gma-extraction-jobs.yaml",
    GraphManagementUiMode.ONE_OFF_MUTATIONS.value: "gma-one-off-mutations.yaml",
}


def regional_vertex_ai_endpoint(*, vertex_region: str) -> str:
    """OpenShell endpoint for a regional Vertex AI hostname (e.g. us-east5-aiplatform.googleapis.com)."""
    region = vertex_region.strip()
    if not region:
        raise ValueError("vertex_region must not be empty")
    return f"{region}-aiplatform.googleapis.com:443:read-write"


def bundled_policy_dir() -> Path:
    return _BUNDLED_POLICY_DIR


def resolve_policy_path(
    *,
    ui_mode: str | None = None,
    workload: Literal["gma", "extraction_job"] = "gma",
    policy_dir: str | None = None,
) -> Path:
    base = Path(policy_dir) if policy_dir else _BUNDLED_POLICY_DIR
    if workload == "extraction_job":
        return base / "extraction-job.yaml"
    if ui_mode and ui_mode in _MODE_POLICY_FILES:
        return base / _MODE_POLICY_FILES[ui_mode]
    return base / "gma-sticky-base.yaml"


def load_policy_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def resolve_endpoints(
    *,
    ui_mode: str | None = None,
    workload: Literal["gma", "extraction_job"] = "gma",
    policy_dir: str | None = None,
    api_host: str | None = None,
    vertex_region: str | None = None,
) -> tuple[str, ...]:
    """Return OpenShell ``policy update --add-endpoint`` strings."""
    path = resolve_policy_path(
        ui_mode=ui_mode, workload=workload, policy_dir=policy_dir
    )
    document = load_policy_yaml(path)
    raw = document.get("endpoints")
    if isinstance(raw, list) and raw:
        endpoints = [str(item).strip() for item in raw if str(item).strip()]
    else:
        endpoints = [_DEFAULT_API_ENDPOINT, _DEFAULT_INFERENCE_ENDPOINT]

    if api_host:
        rewritten: list[str] = []
        for endpoint in endpoints:
            parts = endpoint.split(":")
            if parts and parts[0] == "api" and len(parts) >= 3:
                access_and_rest = ":".join(parts[2:])
                rewritten.append(f"{api_host}:{access_and_rest}")
            else:
                rewritten.append(endpoint)
        endpoints = rewritten
    if vertex_region and vertex_region.strip():
        regional = regional_vertex_ai_endpoint(vertex_region=vertex_region)
        if regional not in endpoints:
            endpoints.append(regional)
    return tuple(endpoints)


def resolve_enforcement(
    *,
    ui_mode: str | None = None,
    workload: Literal["gma", "extraction_job"] = "gma",
    policy_dir: str | None = None,
    default: PolicyEnforcement = "hard_requirement",
) -> PolicyEnforcement:
    path = resolve_policy_path(
        ui_mode=ui_mode, workload=workload, policy_dir=policy_dir
    )
    document = load_policy_yaml(path)
    configured = str(document.get("enforcement", default)).strip()
    if configured in {"soft", "hard_requirement"}:
        return configured  # type: ignore[return-value]
    env_override = os.getenv("KARTOGRAPH_OPENSHELL_POLICY_ENFORCEMENT", "").strip()
    if env_override in {"soft", "hard_requirement"}:
        return env_override  # type: ignore[return-value]
    return default


def resolve_l7_paths(
    *,
    ui_mode: str | None = None,
    workload: Literal["gma", "extraction_job"] = "gma",
    policy_dir: str | None = None,
) -> tuple[str, ...]:
    path = resolve_policy_path(
        ui_mode=ui_mode, workload=workload, policy_dir=policy_dir
    )
    document = load_policy_yaml(path)
    raw = document.get("l7_allowed_paths")
    if not isinstance(raw, list):
        return ()
    return tuple(str(item).strip() for item in raw if str(item).strip())
