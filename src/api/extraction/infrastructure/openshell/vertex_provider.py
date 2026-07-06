"""Ensure OpenShell google-vertex-ai provider for Vertex-backed agent sandboxes."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Literal

from extraction.infrastructure.openshell.cli import OpenShellCliError, run_openshell

AuthMode = Literal["vertex", "api-key"]


def _adc_path(*, gcloud_config_mount: str | None) -> Path:
    if gcloud_config_mount:
        return (
            Path(gcloud_config_mount).expanduser()
            / "application_default_credentials.json"
        )
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


@contextmanager
def _home_for_adc(*, gcloud_config_mount: str | None) -> Iterator[None]:
    """Point HOME at a scratch dir whose ``.config/gcloud`` resolves the mounted ADC.

    ``--from-gcloud-adc`` resolves credentials via the gcloud SDK convention of
    ``$HOME/.config/gcloud/application_default_credentials.json``. The mount
    itself is not guaranteed to already sit two directories below a usable
    HOME (dev compose mounts ``$HOME/.config/gcloud`` directly, but prod
    mounts a flat Vault-sourced secret at e.g. ``/var/secrets/gcloud``), so
    build the nested layout explicitly instead of assuming one.
    """
    if not gcloud_config_mount:
        yield
        return
    adc_source = _adc_path(gcloud_config_mount=gcloud_config_mount)
    with tempfile.TemporaryDirectory(prefix="kartograph-adc-home-") as scratch_home:
        gcloud_dir = Path(scratch_home) / ".config" / "gcloud"
        gcloud_dir.mkdir(parents=True, exist_ok=True)
        (gcloud_dir / "application_default_credentials.json").symlink_to(adc_source)
        previous = os.environ.get("HOME")
        os.environ["HOME"] = scratch_home
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = previous


def provider_exists(*, provider_name: str) -> bool:
    result = run_openshell(
        ["provider", "get", provider_name], check=False, timeout=15.0
    )
    return result.returncode == 0


def _adc_credential_type(*, gcloud_config_mount: str | None) -> str:
    adc = _adc_path(gcloud_config_mount=gcloud_config_mount)
    if not adc.is_file():
        return "unknown"
    try:
        data = json.loads(adc.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    return str(data.get("type", "unknown"))


def ensure_vertex_provider(
    *,
    provider_name: str,
    project_id: str,
    region: str,
    gcloud_config_mount: str | None = None,
    auth_mode: AuthMode = "vertex",
    model: str = "",
) -> None:
    """Create or reuse an OpenShell provider that injects Vertex credentials into sandboxes."""
    if provider_exists(provider_name=provider_name):
        if auth_mode == "vertex":
            ensure_inference_routing(provider_name=provider_name, model=model)
        return

    if auth_mode == "api-key":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise OpenShellCliError(
                "ANTHROPIC_API_KEY is required for OpenShell anthropic provider auth mode"
            )
        run_openshell(
            [
                "provider",
                "create",
                "--name",
                provider_name,
                "--type",
                "anthropic",
                "--credential",
                "ANTHROPIC_API_KEY",
            ],
            timeout=60.0,
        )
        return

    adc = _adc_path(gcloud_config_mount=gcloud_config_mount)
    if not adc.is_file():
        raise OpenShellCliError(
            f"Google ADC not found at {adc}. Run `gcloud auth application-default login` "
            "on the host or set KARTOGRAPH_GCLOUD_CONFIG_MOUNT."
        )

    cred_type = _adc_credential_type(gcloud_config_mount=gcloud_config_mount)
    if cred_type not in {"authorized_user", "service_account"}:
        raise OpenShellCliError(
            f"Unsupported ADC credential type {cred_type!r} at {adc}. "
            "Expected authorized_user or service_account."
        )

    args = [
        "provider",
        "create",
        "--name",
        provider_name,
        "--type",
        "google-vertex-ai",
        "--from-gcloud-adc",
    ]
    if project_id.strip():
        args.extend(["--config", f"VERTEX_AI_PROJECT_ID={project_id.strip()}"])
    if region.strip():
        args.extend(["--config", f"VERTEX_AI_REGION={region.strip()}"])

    with _home_for_adc(gcloud_config_mount=gcloud_config_mount):
        run_openshell(args, timeout=60.0)
    if auth_mode == "vertex":
        ensure_inference_routing(provider_name=provider_name, model=model)


def ensure_inference_routing(*, provider_name: str, model: str) -> None:
    """Point sandbox inference.local at the configured Vertex provider."""
    resolved_model = model.strip() or "claude-opus-4-6"
    run_openshell(
        [
            "inference",
            "set",
            "--provider",
            provider_name,
            "--model",
            resolved_model,
            "--no-verify",
        ],
        timeout=60.0,
    )
