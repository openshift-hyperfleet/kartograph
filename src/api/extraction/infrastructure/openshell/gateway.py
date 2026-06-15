"""OpenShell gateway lifecycle helpers."""

from __future__ import annotations

from extraction.infrastructure.openshell.cli import OpenShellCliError, run_openshell


def gateway_is_registered(*, gateway_name: str) -> bool:
    result = run_openshell(
        ["gateway", "--gateway", gateway_name, "info"],
        check=False,
    )
    return result.returncode == 0


def gateway_is_connected() -> bool:
    result = run_openshell(["status"], check=False)
    if result.returncode != 0:
        return False
    output = f"{result.stdout or ''}\n{result.stderr or ''}"
    if "No gateway configured" in output:
        return False
    return "Connected" in output


def ensure_gateway_registered(*, gateway_name: str, gateway_url: str) -> None:
    """Verify the OpenShell gateway is registered and reachable.

    Registration and mTLS material are expected to be provisioned on the host
    (systemd user service + `openshell gateway add`). Kartograph does not run
    `gateway add` when a registration already exists — that path fails inside
    compose when config is bind-mounted read-only or HOME differs from the host.
    """
    if gateway_is_registered(gateway_name=gateway_name):
        if gateway_is_connected():
            return
        raise OpenShellCliError(
            f"OpenShell gateway '{gateway_name}' is registered but not reachable at "
            f"{gateway_url}. Ensure openshell-gateway is running on the host. For "
            "compose dev, gateway.toml should include "
            'bind_address = "0.0.0.0:17670" and the API container needs '
            "XDG_CONFIG_HOME=/root/.config with the host ~/.config/openshell mount."
        )

    if gateway_is_connected():
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
