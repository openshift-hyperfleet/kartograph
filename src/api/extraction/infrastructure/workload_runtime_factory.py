"""Factory helpers for extraction workload runtime adapters."""

from __future__ import annotations

from datetime import timedelta

from extraction.infrastructure.container_workload_runtime import (
    ContainerEphemeralExtractionWorkerLauncher,
    ContainerStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_runtime import (
    InMemoryEphemeralExtractionWorkerLauncher,
    InMemoryStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
from extraction.ports.runtime import (
    IEphemeralExtractionWorkerLauncher,
    IStickySessionRuntimeManager,
)
from shared_kernel.container_runtime.factory import create_container_runtime


def create_sticky_session_runtime_manager(
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> IStickySessionRuntimeManager:
    """Build sticky runtime manager for configured backend."""
    resolved = settings or get_extraction_workload_runtime_settings()
    if resolved.backend == "memory":
        return InMemoryStickySessionRuntimeManager(
            session_ttl=timedelta(minutes=resolved.session_ttl_minutes)
        )

    container_runtime = create_container_runtime(resolved.container_engine)
    return ContainerStickySessionRuntimeManager(
        container_runtime=container_runtime,
        sticky_image=resolved.sticky_image,
        sticky_command=resolved.sticky_command,
        session_ttl=timedelta(minutes=resolved.session_ttl_minutes),
    )


def create_ephemeral_extraction_worker_launcher(
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> IEphemeralExtractionWorkerLauncher:
    """Build ephemeral worker launcher for configured backend."""
    resolved = settings or get_extraction_workload_runtime_settings()
    if resolved.backend == "memory":
        return InMemoryEphemeralExtractionWorkerLauncher()

    container_runtime = create_container_runtime(resolved.container_engine)
    return ContainerEphemeralExtractionWorkerLauncher(
        container_runtime=container_runtime,
        worker_image=resolved.worker_image,
        worker_command=resolved.worker_command,
    )
