"""Unit tests for OpenShell Vertex provider setup."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from extraction.infrastructure.openshell.cli import OpenShellCliError
from extraction.infrastructure.openshell.vertex_provider import ensure_vertex_provider


def test_ensure_vertex_provider_skips_when_provider_exists() -> None:
    with patch(
        "extraction.infrastructure.openshell.vertex_provider.provider_exists",
        return_value=True,
    ) as exists, patch(
        "extraction.infrastructure.openshell.vertex_provider.ensure_inference_routing",
    ) as inference, patch(
        "extraction.infrastructure.openshell.vertex_provider.run_openshell",
    ) as run:
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

    with patch(
        "extraction.infrastructure.openshell.vertex_provider.provider_exists",
        return_value=False,
    ), patch(
        "extraction.infrastructure.openshell.vertex_provider.ensure_inference_routing",
    ) as inference, patch(
        "extraction.infrastructure.openshell.vertex_provider.run_openshell",
    ) as run:
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
