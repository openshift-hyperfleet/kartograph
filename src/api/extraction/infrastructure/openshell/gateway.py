"""OpenShell gateway lifecycle helpers."""

from __future__ import annotations

from extraction.infrastructure.openshell.cli import run_openshell


def gateway_is_running() -> bool:
    result = run_openshell(["status"], check=False)
    if result.returncode != 0:
        return False
    return "No gateway configured" not in (result.stdout or "")


def ensure_gateway_registered(*, gateway_name: str, gateway_url: str) -> None:
    """Ensure a gateway is registered without starting local podman services."""
    if gateway_is_running():
        return
    run_openshell(
        [
            "gateway",
            "add",
            gateway_url,
            "--local",
            "--name",
            gateway_name,
        ],
        timeout=30.0,
    )
