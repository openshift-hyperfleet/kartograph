"""Shared OpenShell CLI environment for Kartograph subprocess invocations."""

from __future__ import annotations

import os

from extraction.infrastructure.workload_runtime_settings import ExtractionWorkloadRuntimeSettings


def apply_openshell_gateway_env(
    *,
    gateway_name: str = "",
    gateway_url: str = "",
    xdg_config_home: str = "",
) -> None:
    """Ensure openshell subprocesses use the Kartograph gateway registration."""
    if xdg_config_home.strip():
        os.environ["XDG_CONFIG_HOME"] = xdg_config_home.strip()
    if gateway_name.strip():
        os.environ["OPENSHELL_GATEWAY"] = gateway_name.strip()
    if gateway_url.strip():
        os.environ["OPENSHELL_GATEWAY_ENDPOINT"] = gateway_url.strip()


def apply_openshell_cli_env(settings: ExtractionWorkloadRuntimeSettings) -> None:
    """Apply OpenShell CLI env from workload runtime settings."""
    apply_openshell_gateway_env(
        gateway_name=settings.openshell_gateway_name,
        gateway_url=settings.openshell_gateway_url,
        xdg_config_home=settings.openshell_xdg_config_home,
    )
