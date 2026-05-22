"""Container runtime abstractions for launching and managing workload containers."""

from shared_kernel.container_runtime.cli_runtime import CliContainerRuntime
from shared_kernel.container_runtime.factory import create_container_runtime
from shared_kernel.container_runtime.ports import (
    ContainerRunResult,
    ContainerRunSpec,
    ContainerRuntimeError,
    IContainerRuntime,
)

__all__ = [
    "CliContainerRuntime",
    "ContainerRunResult",
    "ContainerRunSpec",
    "ContainerRuntimeError",
    "IContainerRuntime",
    "create_container_runtime",
]
