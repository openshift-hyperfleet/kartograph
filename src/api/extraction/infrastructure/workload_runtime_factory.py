"""Factory helpers for extraction workload runtime adapters."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from extraction.infrastructure.container_workload_runtime import (
    ContainerEphemeralExtractionWorkerLauncher,
    ContainerStickySessionRuntimeManager,
)
from extraction.infrastructure.deterministic_chat_agent import DeterministicExtractionChatAgent
from extraction.infrastructure.remote_sticky_container_chat_agent import (
    RemoteStickyContainerChatAgent,
)
from extraction.infrastructure.workload_runtime import (
    InMemoryEphemeralExtractionWorkerLauncher,
    InMemoryStickySessionRuntimeManager,
    ScopedWorkloadCredentialIssuer,
)
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
from extraction.ports.chat_agent import IExtractionChatAgent
from extraction.ports.runtime import (
    IEphemeralExtractionWorkerLauncher,
    IStickySessionRuntimeManager,
)
from shared_kernel.container_runtime.factory import create_container_runtime


@lru_cache
def get_workload_credential_issuer() -> ScopedWorkloadCredentialIssuer:
    """Return shared workload credential issuer for runtime containers."""
    settings = get_extraction_workload_runtime_settings()
    return ScopedWorkloadCredentialIssuer(
        default_ttl=timedelta(minutes=settings.session_ttl_minutes)
    )


def create_extraction_chat_agent(
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> IExtractionChatAgent:
    """Build chat agent implementation for configured runtime backend."""
    resolved = settings or get_extraction_workload_runtime_settings()
    if resolved.backend == "container":
        return RemoteStickyContainerChatAgent()
    return DeterministicExtractionChatAgent()


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
        container_network=resolved.container_network,
        sticky_service_port=resolved.sticky_service_port,
        container_skills_mount=resolved.container_skills_mount,
        container_work_mount=resolved.container_work_mount,
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
