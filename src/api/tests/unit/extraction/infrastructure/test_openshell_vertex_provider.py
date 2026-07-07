"""Unit tests for OpenShell Vertex provider setup."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from extraction.infrastructure.openshell.cli import OpenShellCliError
from extraction.infrastructure.openshell.vertex_provider import (
    _home_for_adc,
    ensure_vertex_provider,
)


def test_ensure_vertex_provider_skips_when_provider_exists() -> None:
    with (
        patch(
            "extraction.infrastructure.openshell.vertex_provider.provider_exists",
            return_value=True,
        ) as exists,
        patch(
            "extraction.infrastructure.openshell.vertex_provider.ensure_inference_routing",
        ) as inference,
        patch(
            "extraction.infrastructure.openshell.vertex_provider.run_openshell",
        ) as run,
    ):
        ensure_vertex_provider(
            provider_name="kartograph-gma",
            project_id="proj",
            region="us-east5",
            model="claude-opus-4-6",
        )

    exists.assert_called_once_with(provider_name="kartograph-gma")
    inference.assert_called_once_with(
        provider_name="kartograph-gma",
        model="claude-opus-4-6",
    )
    run.assert_not_called()


def test_ensure_vertex_provider_creates_google_vertex_ai_from_adc(tmp_path) -> None:
    adc_dir = tmp_path / "gcloud"
    adc_dir.mkdir()
    adc_file = adc_dir / "application_default_credentials.json"
    adc_file.write_text('{"type":"authorized_user"}', encoding="utf-8")

    with (
        patch(
            "extraction.infrastructure.openshell.vertex_provider.provider_exists",
            return_value=False,
        ),
        patch(
            "extraction.infrastructure.openshell.vertex_provider.ensure_inference_routing",
        ) as inference,
        patch(
            "extraction.infrastructure.openshell.vertex_provider.run_openshell",
        ) as run,
    ):
        ensure_vertex_provider(
            provider_name="kartograph-gma",
            project_id="my-project",
            region="us-east5",
            gcloud_config_mount=str(adc_dir),
            model="claude-opus-4-6",
        )

    run.assert_called_once()
    args = run.call_args.args[0]
    assert args[:4] == ["provider", "create", "--name", "kartograph-gma"]
    assert "google-vertex-ai" in args
    assert "--from-gcloud-adc" in args
    assert "VERTEX_AI_PROJECT_ID=my-project" in args
    assert "VERTEX_AI_REGION=us-east5" in args
    inference.assert_called_once_with(
        provider_name="kartograph-gma",
        model="claude-opus-4-6",
    )


def _adc_lookup_path_from_home() -> Path:
    """Where gcloud/OpenShell's ``--from-gcloud-adc`` looks, given the active HOME."""
    return (
        Path(os.environ["HOME"])
        / ".config"
        / "gcloud"
        / "application_default_credentials.json"
    )


def test_home_for_adc_resolves_nested_dev_style_mount(tmp_path) -> None:
    """Dev compose mounts the host's real ``$HOME/.config/gcloud`` directly."""
    fake_home = tmp_path / "home" / "dev"
    gcloud_dir = fake_home / ".config" / "gcloud"
    gcloud_dir.mkdir(parents=True)
    adc_file = gcloud_dir / "application_default_credentials.json"
    adc_file.write_text('{"type":"authorized_user"}', encoding="utf-8")

    with _home_for_adc(gcloud_config_mount=str(gcloud_dir)):
        assert _adc_lookup_path_from_home().read_text(encoding="utf-8") == (
            adc_file.read_text(encoding="utf-8")
        )


def test_home_for_adc_resolves_flat_prod_style_mount(tmp_path) -> None:
    """Prod mounts a Vault-sourced secret flatly (not nested under a home dir).

    Regression test: OpenShift mounts the ``kartograph-extraction-runtime``
    ExternalSecret at ``/var/secrets/gcloud`` (see hp-fleet-gitops
    apps/kartograph/base/api-deployment.yaml), so the mount is *not* two
    directories below a usable HOME. ``_home_for_adc`` must still produce a
    HOME whose ``.config/gcloud/application_default_credentials.json``
    resolves to the actual mounted ADC file.
    """
    flat_mount = tmp_path / "var" / "secrets" / "gcloud"
    flat_mount.mkdir(parents=True)
    adc_file = flat_mount / "application_default_credentials.json"
    adc_file.write_text('{"type":"service_account"}', encoding="utf-8")

    with _home_for_adc(gcloud_config_mount=str(flat_mount)):
        assert _adc_lookup_path_from_home().read_text(encoding="utf-8") == (
            adc_file.read_text(encoding="utf-8")
        )


def test_home_for_adc_restores_previous_home(tmp_path) -> None:
    flat_mount = tmp_path / "secrets" / "gcloud"
    flat_mount.mkdir(parents=True)
    (flat_mount / "application_default_credentials.json").write_text(
        "{}", encoding="utf-8"
    )

    previous = os.environ.get("HOME")
    with _home_for_adc(gcloud_config_mount=str(flat_mount)):
        assert os.environ.get("HOME") != previous
    assert os.environ.get("HOME") == previous


def test_ensure_vertex_provider_enriches_create_failure_with_profile_diagnostic(
    tmp_path,
) -> None:
    """On create failure, append a live `provider profile export` dump.

    OpenShell's generic "no credentials resolved" error for google-vertex-ai
    hides whether the gateway's served profile actually allows empty-credential
    bootstrap (see openshell-cli run.rs `missing_credentials_error`). Since
    that can only be observed against the real gateway at failure time,
    surface it inline so it lands in the sticky-runtime probe's error field.
    """
    adc_dir = tmp_path / "gcloud"
    adc_dir.mkdir()
    (adc_dir / "application_default_credentials.json").write_text(
        '{"type":"authorized_user"}', encoding="utf-8"
    )

    import subprocess

    diagnostic_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"id": "google-vertex-ai", "credentials": []}',
        stderr="",
    )

    with (
        patch(
            "extraction.infrastructure.openshell.vertex_provider.provider_exists",
            return_value=False,
        ),
        patch(
            "extraction.infrastructure.openshell.vertex_provider.run_openshell",
            side_effect=[
                OpenShellCliError(
                    "openshell provider create ... failed: no credentials resolved"
                ),
                diagnostic_result,
            ],
        ) as run,
    ):
        with pytest.raises(OpenShellCliError) as exc_info:
            ensure_vertex_provider(
                provider_name="kartograph-gma",
                project_id="my-project",
                region="us-east5",
                gcloud_config_mount=str(adc_dir),
            )

    assert "no credentials resolved" in str(exc_info.value)
    assert '"id": "google-vertex-ai"' in str(exc_info.value)
    assert run.call_count == 2
    diagnostic_args = run.call_args_list[1].args[0]
    assert diagnostic_args == [
        "provider",
        "profile",
        "export",
        "google-vertex-ai",
        "--output",
        "json",
    ]


def test_ensure_vertex_provider_raises_when_adc_missing(tmp_path) -> None:
    with patch(
        "extraction.infrastructure.openshell.vertex_provider.provider_exists",
        return_value=False,
    ):
        with pytest.raises(OpenShellCliError, match="Google ADC not found"):
            ensure_vertex_provider(
                provider_name="kartograph-gma",
                project_id="proj",
                region="us-east5",
                gcloud_config_mount=str(tmp_path / "missing"),
            )
