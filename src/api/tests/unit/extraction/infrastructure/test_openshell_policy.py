"""Unit tests for OpenShell policy resolution."""

from __future__ import annotations

from extraction.infrastructure.openshell.policy import (
    bundled_policy_dir,
    regional_vertex_ai_endpoint,
    resolve_endpoints,
    resolve_enforcement,
    resolve_l7_paths,
    resolve_policy_path,
)


def test_resolve_policy_path_by_ui_mode() -> None:
    path = resolve_policy_path(ui_mode="initial-schema-design")
    assert path.name == "gma-initial-schema-design.yaml"


def test_resolve_endpoints_rewrites_api_host() -> None:
    endpoints = resolve_endpoints(
        ui_mode="one-off-mutations",
        api_host="kartograph-api:8000",
    )
    assert "kartograph-api:8000:read-write" in endpoints
    assert "inference.local:443:read-write" in endpoints


def test_resolve_enforcement_from_bundled_policy() -> None:
    enforcement = resolve_enforcement(ui_mode="initial-schema-design")
    assert enforcement == "hard_requirement"


def test_resolve_enforcement_for_extraction_job_policy() -> None:
    enforcement = resolve_enforcement(workload="extraction_job")
    assert enforcement == "hard_requirement"


def test_resolve_endpoints_includes_vertex_oauth_for_gma_modes() -> None:
    endpoints = resolve_endpoints(ui_mode="extraction-jobs")
    assert "oauth2.googleapis.com:443:read-write" in endpoints
    assert "aiplatform.googleapis.com:443:read-write" in endpoints


def test_resolve_endpoints_adds_regional_vertex_hostname() -> None:
    endpoints = resolve_endpoints(
        ui_mode="extraction-jobs",
        api_host="host.docker.internal:8000",
        vertex_region="us-east5",
    )
    assert "us-east5-aiplatform.googleapis.com:443:read-write" in endpoints
    assert "host.docker.internal:8000:read-write" in endpoints


def test_regional_vertex_ai_endpoint() -> None:
    assert (
        regional_vertex_ai_endpoint(vertex_region="us-east5")
        == "us-east5-aiplatform.googleapis.com:443:read-write"
    )


def test_resolve_l7_paths_for_extraction_jobs_mode() -> None:
    paths = resolve_l7_paths(ui_mode="extraction-jobs")
    assert any("jobs" in path for path in paths)


def test_bundled_policy_dir_exists() -> None:
    assert bundled_policy_dir().is_dir()
