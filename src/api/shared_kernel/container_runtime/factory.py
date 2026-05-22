"""Factory helpers for container runtime backends."""

from __future__ import annotations

import shutil

from shared_kernel.container_runtime.cli_runtime import CliContainerRuntime
from shared_kernel.container_runtime.ports import ContainerRuntimeError, IContainerRuntime


def create_container_runtime(engine: str = "auto") -> IContainerRuntime:
    """Return a CLI container runtime for the requested engine."""
    binary = _resolve_engine_binary(engine)
    return CliContainerRuntime(binary=binary)


def _resolve_engine_binary(engine: str) -> str:
    if engine == "auto":
        for candidate in ("docker", "podman"):
            if shutil.which(candidate) is not None:
                return candidate
        raise ContainerRuntimeError("No docker or podman binary found on PATH")

    if engine not in {"docker", "podman"}:
        raise ContainerRuntimeError(f"Unsupported container engine: {engine}")

    if shutil.which(engine) is None:
        raise ContainerRuntimeError(f"{engine} binary not found on PATH")

    return engine
