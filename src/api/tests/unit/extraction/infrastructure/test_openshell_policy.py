"""Unit tests for OpenShell policy resolution."""

from __future__ import annotations

from extraction.infrastructure.openshell.policy import (
    bundled_policy_dir,
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
    assert enforcement in {"soft", "hard_requirement"}


def test_resolve_l7_paths_for_extraction_jobs_mode() -> None:
    paths = resolve_l7_paths(ui_mode="extraction-jobs")
    assert any("jobs" in path for path in paths)


def test_bundled_policy_dir_exists() -> None:
    assert bundled_policy_dir().is_dir()
