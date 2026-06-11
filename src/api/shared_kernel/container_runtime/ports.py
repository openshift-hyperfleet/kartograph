"""Port contracts for container runtime backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ContainerRuntimeError(RuntimeError):
    """Raised when a container runtime operation fails."""


@dataclass(frozen=True)
class ContainerRunSpec:
    """Launch parameters for a detached container."""

    image: str
    name: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    command: tuple[str, ...] | None = None
    binds: tuple[str, ...] = field(default_factory=tuple)
    network: str | None = None
    detach: bool = True
    remove_on_exit: bool = False
    user: str | None = None


@dataclass(frozen=True)
class ContainerRunResult:
    """Result of a successful container launch."""

    container_id: str
    name: str | None


class IContainerRuntime(Protocol):
    """Backend-neutral container lifecycle operations."""

    def run(self, spec: ContainerRunSpec) -> ContainerRunResult:
        """Launch a container and return its identifier."""
        ...

    def stop(self, container_id: str, *, timeout_seconds: int = 10) -> None:
        """Stop a running container."""
        ...

    def remove(self, container_id: str, *, force: bool = False) -> None:
        """Remove a stopped container."""
        ...

    def is_running(self, container_id: str) -> bool:
        """Return True when the container exists and is running."""
        ...

    def container_id_for_name(self, name: str) -> str | None:
        """Return the running container ID for a fixed container name, if any."""
        ...

    def remove_by_name(self, name: str, *, force: bool = True) -> bool:
        """Remove a container by name. Returns True when a container was removed."""
        ...
