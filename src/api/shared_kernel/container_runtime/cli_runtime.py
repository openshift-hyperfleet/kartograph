"""CLI-backed container runtime using docker or podman."""

from __future__ import annotations

import subprocess
from typing import Final

from shared_kernel.container_runtime.ports import (
    ContainerRunResult,
    ContainerRunSpec,
    ContainerRuntimeError,
)


class CliContainerRuntime:
    """Launch and manage containers through a docker-compatible CLI."""

    _RUNNING_TEMPLATE: Final[str] = "{{.State.Running}}"

    def __init__(self, *, binary: str) -> None:
        self._binary = binary

    def run(self, spec: ContainerRunSpec) -> ContainerRunResult:
        command = [self._binary, "run"]
        if spec.detach:
            command.append("--detach")
        if spec.remove_on_exit:
            command.append("--rm")
        if spec.name is not None:
            command.extend(["--name", spec.name])
        for key, value in sorted(spec.labels.items()):
            command.extend(["--label", f"{key}={value}"])
        for key, value in sorted(spec.env.items()):
            command.extend(["--env", f"{key}={value}"])
        for bind in spec.binds:
            command.extend(["--volume", bind])
        if spec.network is not None:
            command.extend(["--network", spec.network])
        if spec.user is not None:
            command.extend(["--user", spec.user])
        command.append(spec.image)
        if spec.command:
            command.extend(spec.command)

        stdout = self._execute(command)
        container_id = stdout.splitlines()[0].strip()
        return ContainerRunResult(container_id=container_id, name=spec.name)

    def stop(self, container_id: str, *, timeout_seconds: int = 10) -> None:
        self._execute([self._binary, "stop", "-t", str(timeout_seconds), container_id])

    def remove(self, container_id: str, *, force: bool = False) -> None:
        command = [self._binary, "rm"]
        if force:
            command.append("-f")
        command.append(container_id)
        self._execute(command)

    def is_running(self, container_id: str) -> bool:
        result = subprocess.run(
            [
                self._binary,
                "inspect",
                "-f",
                self._RUNNING_TEMPLATE,
                container_id,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            if "no such" in detail.lower():
                return False
            raise ContainerRuntimeError(
                f"{self._binary} inspect failed: {detail or 'unknown error'}"
            )
        return result.stdout.strip().lower() == "true"

    def container_id_for_name(self, name: str) -> str | None:
        """Return the running container ID for a fixed container name, if any."""
        container_id = self._inspect_container_id(name)
        if container_id is None:
            return None
        if not self.is_running(container_id):
            return None
        return container_id

    def remove_by_name(self, name: str, *, force: bool = True) -> bool:
        """Remove a container by name. Returns True when a container was removed."""
        if self._inspect_container_id(name) is None:
            return False
        command = [self._binary, "rm"]
        if force:
            command.append("-f")
        command.append(name)
        self._execute(command)
        return True

    def _inspect_container_id(self, name: str) -> str | None:
        result = subprocess.run(
            [self._binary, "inspect", "-f", "{{.Id}}", name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        container_id = result.stdout.strip()
        return container_id or None

    def _execute(self, command: list[str]) -> str:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise ContainerRuntimeError(
                f"{self._binary} {' '.join(command[1:])} failed: {detail}"
            )
        return result.stdout
