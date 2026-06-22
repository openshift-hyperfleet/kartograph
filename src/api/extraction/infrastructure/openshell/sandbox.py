"""OpenShell sandbox lifecycle operations."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

from extraction.infrastructure.openshell.audit import (
    LoggingOpenShellRuntimeProbe,
    OpenShellPolicyAppliedObservation,
    OpenShellRuntimeProbe,
    OpenShellSandboxLifecycleObservation,
)
from extraction.infrastructure.openshell.cli import (
    OpenShellCliError,
    openshell_subprocess_env,
    popen_openshell,
    run_openshell,
)
from extraction.infrastructure.openshell.policy import (
    resolve_endpoints,
    resolve_enforcement,
)
from extraction.infrastructure.vertex_runtime_env import GCLOUD_ADC_FILENAME

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")
_FAILURE_PHASES = frozenset({"Error", "Failed", "Terminating"})


def sanitize_sandbox_name(prefix: str, identifier: str) -> str:
    cleaned = _CONTAINER_NAME_SAFE.sub("-", identifier).strip("-")
    name = f"{prefix}{cleaned}"
    return name[:63].rstrip("-_.") or f"{prefix}runtime"


def sandbox_exists(name: str) -> bool:
    result = run_openshell(["sandbox", "get", name], check=False)
    return result.returncode == 0


def sandbox_phase(name: str) -> str | None:
    result = run_openshell(["sandbox", "list", "-o", "json"], check=False)
    if result.returncode != 0:
        return None
    try:
        sandboxes = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not isinstance(sandboxes, list):
        return None
    for item in sandboxes:
        if isinstance(item, dict) and item.get("name") == name:
            phase = item.get("phase")
            return str(phase) if phase is not None else None
    return None


def _wait_for_sandbox_ready(*, name: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        phase = sandbox_phase(name)
        if phase == "Ready":
            return
        if phase in _FAILURE_PHASES:
            detail = run_openshell(["sandbox", "get", name], check=False)
            message = (detail.stderr or detail.stdout or "").strip() or f"phase={phase}"
            raise OpenShellCliError(f"sandbox {name} entered {phase}: {message}")
        time.sleep(0.5)
    raise OpenShellCliError(f"timed out waiting for sandbox {name} to become Ready")


def _terminate_create_process(proc) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5.0)
    except Exception:
        proc.kill()
        proc.wait(timeout=5.0)


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
    proc = popen_openshell(args)
    try:
        _wait_for_sandbox_ready(name=name, timeout=300.0)
    finally:
        _terminate_create_process(proc)


def delete_sandbox(name: str) -> None:
    if not sandbox_exists(name):
        return
    run_openshell(["sandbox", "delete", name], check=False, timeout=120.0)


def list_sandbox_names() -> list[str]:
    """Return sandbox names from the active OpenShell gateway."""
    result = run_openshell(["sandbox", "list", "-o", "json"], check=False, timeout=30.0)
    if result.returncode != 0:
        return []
    try:
        sandboxes = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(sandboxes, list):
        return []
    names: list[str] = []
    for item in sandboxes:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def delete_sandboxes_by_prefix(prefix: str) -> int:
    """Delete all sandboxes whose names start with prefix. Returns count deleted."""
    deleted = 0
    for name in list_sandbox_names():
        if name.startswith(prefix):
            delete_sandbox(name)
            deleted += 1
    return deleted


def extraction_job_sandbox_name(job_id: str) -> str:
    return sanitize_sandbox_name("kartograph-extract-", job_id)


def stop_extraction_job_sandbox(*, job_id: str) -> bool:
    """Delete the OpenShell sandbox for one extraction job, if it exists."""
    name = extraction_job_sandbox_name(job_id)
    if not sandbox_exists(name):
        return False
    delete_sandbox(name)
    return True


def stop_extraction_job_sandboxes(
    *,
    job_ids: tuple[str, ...] | list[str],
) -> int:
    """Delete OpenShell sandboxes for extraction jobs. Returns count deleted."""
    stopped = 0
    for job_id in job_ids:
        if stop_extraction_job_sandbox(job_id=job_id):
            stopped += 1
    return stopped


def upload_path(*, sandbox_name: str, local_path: str, dest: str | None = None) -> None:
    args = ["sandbox", "upload", "--no-git-ignore", sandbox_name, local_path]
    if dest:
        args.append(dest)
    run_openshell(args, timeout=600.0)


def download_path(*, sandbox_name: str, sandbox_path: str, local_path: str) -> None:
    """Download a sandbox file into a local path (parent directory is created)."""
    destination = Path(local_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run_openshell(
        ["sandbox", "download", sandbox_name, sandbox_path, str(destination.parent)],
        timeout=120.0,
    )
    # OpenShell writes basename(sandbox_path) into the destination directory.
    downloaded = destination.parent / Path(sandbox_path).name
    if downloaded != destination:
        if not downloaded.is_file():
            raise OpenShellCliError(
                f"openshell download did not create expected file at {downloaded}"
            )
        if destination.exists():
            destination.unlink()
        downloaded.rename(destination)


def upload_directory_contents(*, sandbox_name: str, local_dir: str, dest: str) -> None:
    """Upload directory contents into dest without nesting under the directory basename.

    ``sandbox upload`` places a directory at ``dest/<basename(local_dir)>``. Agent
    runtimes expect job package files at the workspace root (``KARTOGRAPH_WORKSPACE_DIR``).
    """
    source = Path(local_dir)
    if not source.is_dir():
        raise ValueError(f"local_dir must be a directory: {local_dir}")

    remote_tar = f"/tmp/kartograph-upload-{sandbox_name}.tar"
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as handle:
        local_tar = Path(handle.name)
    try:
        with tarfile.open(local_tar, "w") as archive:
            for entry in sorted(source.iterdir()):
                archive.add(entry, arcname=entry.name)
        upload_path(
            sandbox_name=sandbox_name, local_path=str(local_tar), dest=remote_tar
        )
        extract_cmd = (
            f"mkdir -p {shlex.quote(dest)} && "
            f"tar -xf {shlex.quote(remote_tar)} -C {shlex.quote(dest)} && "
            f"rm -f {shlex.quote(remote_tar)}"
        )
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
                extract_cmd,
            ],
            timeout=600.0,
        )
    finally:
        local_tar.unlink(missing_ok=True)


def _safe_extract_tar(archive: tarfile.TarFile, destination: Path) -> None:
    """Extract tar members only under destination, rejecting path traversal."""
    target = destination.resolve()
    target.mkdir(parents=True, exist_ok=True)
    for member in archive.getmembers():
        member_path = (target / member.name).resolve()
        if not member_path.is_relative_to(target):
            raise OpenShellCliError(
                f"tar member {member.name!r} escapes extraction directory {target}"
            )
    archive.extractall(target, filter="data")


def download_directory_contents(
    *,
    sandbox_name: str,
    remote_dir: str,
    local_dir: Path,
) -> None:
    """Download a sandbox directory tree into a local directory."""
    remote = remote_dir.rstrip("/")
    remote_name = Path(remote).name
    remote_parent = str(Path(remote).parent) or "/"
    remote_tar = f"/tmp/kartograph-download-{sandbox_name}.tar"

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
            (
                f"test -d {shlex.quote(remote)} && "
                f"tar -cf {shlex.quote(remote_tar)} -C {shlex.quote(remote_parent)} "
                f"{shlex.quote(remote_name)}"
            ),
        ],
        timeout=120.0,
    )

    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as handle:
        local_tar = Path(handle.name)
    try:
        download_path(
            sandbox_name=sandbox_name,
            sandbox_path=remote_tar,
            local_path=str(local_tar),
        )
        local_dir.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(local_tar, "r") as archive:
            _safe_extract_tar(archive, local_dir)
        run_openshell(
            [
                "sandbox",
                "exec",
                "--name",
                sandbox_name,
                "--no-tty",
                "--",
                "rm",
                "-f",
                remote_tar,
            ],
            check=False,
            timeout=30.0,
        )
    finally:
        local_tar.unlink(missing_ok=True)


def upload_gcloud_adc(
    *,
    sandbox_name: str,
    host_gcloud_config_dir: str,
    container_config_path: str,
) -> None:
    """Upload host Application Default Credentials into an OpenShell sandbox."""
    host_adc = Path(host_gcloud_config_dir).expanduser() / GCLOUD_ADC_FILENAME
    if not host_adc.is_file():
        raise OpenShellCliError(
            f"Google ADC not found at {host_adc}. "
            "Run `gcloud auth application-default login` on the host, or set "
            "KARTOGRAPH_GCLOUD_CONFIG_MOUNT to your ~/.config/gcloud directory."
        )

    remote_dir = container_config_path.rstrip("/")
    remote_adc = f"{remote_dir}/{GCLOUD_ADC_FILENAME}"
    prepare_cmd = (
        f"mkdir -p {shlex.quote(remote_dir)} && chmod 755 {shlex.quote(remote_dir)}"
    )
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
            prepare_cmd,
        ],
        timeout=60.0,
    )
    upload_path(sandbox_name=sandbox_name, local_path=str(host_adc), dest=remote_adc)
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
            f"chmod a+r {shlex.quote(remote_adc)}",
        ],
        timeout=60.0,
    )


_GMA_POLICY_BINARIES = ("/app/.venv/bin/python",)
_EXTRACTION_POLICY_BINARIES = ("/usr/local/bin/claude", "/usr/bin/opencode")


def apply_policy(
    *,
    sandbox_name: str,
    ui_mode: str | None = None,
    workload: str = "gma",
    policy_dir: str | None = None,
    api_host: str | None = None,
    vertex_region: str | None = None,
    policy_enforcement: str = "hard_requirement",
    policy_binaries: tuple[str, ...] | None = None,
    probe: OpenShellRuntimeProbe | None = None,
) -> None:
    endpoints = resolve_endpoints(
        ui_mode=ui_mode,
        workload=workload,  # type: ignore[arg-type]
        policy_dir=policy_dir,
        api_host=api_host,
        vertex_region=vertex_region,
    )
    enforcement = resolve_enforcement(
        ui_mode=ui_mode,
        workload=workload,  # type: ignore[arg-type]
        policy_dir=policy_dir,
        default=policy_enforcement,  # type: ignore[arg-type]
    )
    if not endpoints:
        return

    binaries = policy_binaries
    if binaries is None:
        binaries = (
            _EXTRACTION_POLICY_BINARIES
            if workload == "extraction_job"
            else _GMA_POLICY_BINARIES
        )

    args = [
        "policy",
        "update",
        "--wait",
    ]
    for binary in binaries:
        args.extend(["--binary", binary])
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


def _forwards_state_dir() -> Path:
    config_home = (
        os.environ.get(
            "KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_XDG_CONFIG_HOME", ""
        ).strip()
        or os.environ.get("XDG_CONFIG_HOME", "").strip()
        or str(Path.home() / ".config")
    )
    return Path(config_home) / "openshell" / "forwards"


def _ensure_forwards_state_dir_writable() -> None:
    forwards_dir = _forwards_state_dir()
    try:
        forwards_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OpenShellCliError(
            f"OpenShell forwards state directory is not writable: {forwards_dir}. "
            "When the API runs in compose, mount a writable volume at "
            "/root/.config/openshell/forwards (see compose.dev.yaml)."
        ) from exc
    if not os.access(forwards_dir, os.W_OK):
        raise OpenShellCliError(
            f"OpenShell forwards state directory is read-only: {forwards_dir}. "
            "openshell forward start -d hangs when it cannot write PID files. "
            "Mount a writable volume at /root/.config/openshell/forwards."
        )


def start_forward(*, sandbox_name: str, port: int, target_port: int = 8787) -> None:
    """Forward a local port to the agent runtime listening inside the sandbox."""
    _ensure_forwards_state_dir_writable()
    command = [
        "openshell",
        "forward",
        "service",
        sandbox_name,
        "--target-port",
        str(target_port),
        "--local",
        str(port),
    ]
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=openshell_subprocess_env(),
        start_new_session=True,
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
    exports = " ".join(
        f"export {key}={shlex.quote(value)};" for key, value in sorted(env.items())
    )
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


def run_sandbox_exec(*, sandbox_name: str, command: list[str]) -> None:
    """Run a command inside a sandbox and raise on failure."""
    run_openshell(
        ["sandbox", "exec", "--name", sandbox_name, "--no-tty", "--", *command],
        timeout=120.0,
    )
