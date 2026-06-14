"""OpenShell sandbox lifecycle operations."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from extraction.infrastructure.openshell.audit import (
    LoggingOpenShellRuntimeProbe,
    OpenShellPolicyAppliedObservation,
    OpenShellRuntimeProbe,
    OpenShellSandboxLifecycleObservation,
)
from extraction.infrastructure.openshell.cli import popen_openshell, run_openshell
from extraction.infrastructure.openshell.policy import resolve_endpoints, resolve_enforcement

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")


def sanitize_sandbox_name(prefix: str, identifier: str) -> str:
    cleaned = _CONTAINER_NAME_SAFE.sub("-", identifier).strip("-")
    name = f"{prefix}{cleaned}"
    return name[:63].rstrip("-_.") or f"{prefix}runtime"


def sandbox_exists(name: str) -> bool:
    result = run_openshell(["sandbox", "get", name], check=False)
    return result.returncode == 0


def create_sandbox(
    *,
    name: str,
    image: str,
    provider_name: str | None = None,
) -> None:
    args = [
        "sandbox",
        "create",
        "--name",
        name,
        "--no-tty",
        "--no-auto-providers",
    ]
    if provider_name:
        args.extend(["--provider", provider_name])
    args.extend(["--from", image, "--", "sleep", "infinity"])
    run_openshell(args, timeout=300.0)


def delete_sandbox(name: str) -> None:
    if not sandbox_exists(name):
        return
    run_openshell(["sandbox", "delete", name], check=False, timeout=120.0)


def upload_path(*, sandbox_name: str, local_path: str, dest: str | None = None) -> None:
    args = ["sandbox", "upload", "--no-git-ignore", sandbox_name, local_path]
    if dest:
        args.extend(["--dest", dest])
    run_openshell(args, timeout=600.0)


def apply_policy(
    *,
    sandbox_name: str,
    ui_mode: str | None = None,
    workload: str = "gma",
    policy_dir: str | None = None,
    api_host: str | None = None,
    policy_enforcement: str = "soft",
    probe: OpenShellRuntimeProbe | None = None,
) -> None:
    endpoints = resolve_endpoints(
        ui_mode=ui_mode,
        workload=workload,  # type: ignore[arg-type]
        policy_dir=policy_dir,
        api_host=api_host,
    )
    enforcement = resolve_enforcement(
        ui_mode=ui_mode,
        workload=workload,  # type: ignore[arg-type]
        policy_dir=policy_dir,
        default=policy_enforcement,  # type: ignore[arg-type]
    )
    if not endpoints:
        return

    args = [
        "policy",
        "update",
        "--wait",
        "--binary",
        "/runtime/.venv/bin/python",
    ]
    if enforcement == "hard_requirement":
        args.extend(["--enforcement", "hard_requirement"])
    for endpoint in endpoints:
        args.extend(["--add-endpoint", endpoint])
    args.append(sandbox_name)
    run_openshell(args, timeout=120.0)

    resolved_probe = probe or LoggingOpenShellRuntimeProbe()
    policy_name = ui_mode or workload
    resolved_probe.policy_applied(
        OpenShellPolicyAppliedObservation(
            sandbox_name=sandbox_name,
            policy_name=policy_name,
            enforcement=enforcement,
            endpoint_count=len(endpoints),
            ui_mode=ui_mode,
        )
    )


def start_forward(*, sandbox_name: str, port: int) -> None:
    run_openshell(
        ["forward", "start", str(port), sandbox_name, "-d"],
        timeout=30.0,
    )


def stop_forward(*, sandbox_name: str, port: int) -> None:
    run_openshell(
        ["forward", "stop", str(port), sandbox_name],
        check=False,
        timeout=30.0,
    )


def exec_background(
    *,
    sandbox_name: str,
    env: dict[str, str],
    command: tuple[str, ...],
) -> None:
    exports = " ".join(f"export {key}={shlex.quote(value)};" for key, value in sorted(env.items()))
    shell_command = f"{exports} exec {' '.join(shlex.quote(part) for part in command)}"
    run_openshell(
        [
            "sandbox",
            "exec",
            "--name",
            sandbox_name,
            "--no-tty",
            "--",
            "bash",
            "-lc",
            f"nohup {shell_command} >/tmp/agent-runtime.log 2>&1 &",
        ],
        timeout=60.0,
    )


def write_env_script(
    *,
    sandbox_name: str,
    env: dict[str, str],
    dest: str = "/tmp/kartograph-runtime-env.sh",
) -> None:
    lines = [f"export {key}={shlex.quote(value)}" for key, value in sorted(env.items())]
    script = "\n".join(lines) + "\n"
    local = Path("/tmp") / f"{sandbox_name}-env.sh"
    local.write_text(script, encoding="utf-8")
    try:
        upload_path(sandbox_name=sandbox_name, local_path=str(local), dest=dest)
    finally:
        local.unlink(missing_ok=True)


def emit_lifecycle(
    *,
    sandbox_name: str,
    action: str,
    probe: OpenShellRuntimeProbe | None = None,
    image: str | None = None,
    forward_port: int | None = None,
    session_id: str | None = None,
    job_id: str | None = None,
) -> None:
    resolved_probe = probe or LoggingOpenShellRuntimeProbe()
    resolved_probe.sandbox_lifecycle(
        OpenShellSandboxLifecycleObservation(
            sandbox_name=sandbox_name,
            action=action,
            image=image,
            forward_port=forward_port,
            session_id=session_id,
            job_id=job_id,
        )
    )


def exec_streaming(*, sandbox_name: str, command: list[str]):
    return popen_openshell(
        ["sandbox", "exec", "--name", sandbox_name, "--no-tty", "--", *command]
    )
