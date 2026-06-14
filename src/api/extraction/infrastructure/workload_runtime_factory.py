"""Factory helpers for extraction workload runtime adapters."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from extraction.infrastructure.container_workload_runtime import (
    ContainerEphemeralExtractionWorkerLauncher,
    ContainerStickySessionRuntimeManager,
)
from extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager import (
    OpenShellStickySessionRuntimeManager,
)
from extraction.infrastructure.deterministic_chat_agent import DeterministicExtractionChatAgent
from extraction.infrastructure.remote_sticky_container_chat_agent import (
    RemoteStickyContainerChatAgent,
)
from extraction.infrastructure.workload_credential_issuer import (
    DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY,
    ScopedWorkloadCredentialIssuer,
)
from extraction.infrastructure.workload_runtime import (
    InMemoryEphemeralExtractionWorkerLauncher,
    InMemoryStickySessionRuntimeManager,
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


def resolve_workload_token_signing_key(
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> str:
    """Return the HMAC key used to sign and verify workload JWTs."""
    resolved = settings or get_extraction_workload_runtime_settings()
    configured = resolved.workload_token_signing_key.strip()
    if configured:
        return configured
    return DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY


@lru_cache
def get_workload_credential_issuer() -> ScopedWorkloadCredentialIssuer:
    """Return shared workload credential issuer for runtime containers."""
    settings = get_extraction_workload_runtime_settings()
    return ScopedWorkloadCredentialIssuer(
        signing_key=resolve_workload_token_signing_key(settings),
        default_ttl=timedelta(minutes=settings.session_ttl_minutes),
    )


def create_extraction_chat_agent(
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> IExtractionChatAgent:
    """Build chat agent implementation for configured runtime backend."""
    resolved = settings or get_extraction_workload_runtime_settings()
    if resolved.backend in {"container", "openshell"}:
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

    if resolved.backend == "openshell":
        return OpenShellStickySessionRuntimeManager(
            sticky_image=resolved.sticky_image,
            session_ttl=timedelta(minutes=resolved.session_ttl_minutes),
            sticky_service_port=resolved.sticky_service_port,
            container_work_mount=resolved.container_work_mount,
            vertex_project_id=resolved.vertex_project_id,
            vertex_region=resolved.vertex_region,
            vertex_enabled=resolved.vertex_enabled(),
            agent_turn_timeout_seconds=resolved.sticky_turn_timeout_seconds,
            agent_max_turns=resolved.sticky_max_turns,
            api_base_url=resolved.api_base_url,
            gateway_name=resolved.openshell_gateway_name,
            gateway_url=resolved.openshell_gateway_url,
            provider_name=resolved.openshell_provider_name,
            runtime_host=resolved.openshell_runtime_host,
            forward_port_base=resolved.openshell_forward_port_base,
            policy_dir=resolved.openshell_policy_dir or None,
            policy_enforcement=resolved.openshell_policy_enforcement,
        )

    container_runtime = create_container_runtime(resolved.container_engine)
    return ContainerStickySessionRuntimeManager(
        container_runtime=container_runtime,
        sticky_image=resolved.sticky_image,
        sticky_command=resolved.sticky_command,
        session_ttl=timedelta(minutes=resolved.session_ttl_minutes),
        container_network=resolved.container_network,
        sticky_service_port=resolved.sticky_service_port,
        container_work_mount=resolved.container_work_mount,
        vertex_project_id=resolved.vertex_project_id,
        vertex_region=resolved.vertex_region,
        vertex_enabled=resolved.vertex_enabled(),
        gcloud_config_mount=resolved.gcloud_config_mount,
        gcloud_config_container_path=resolved.gcloud_config_container_path,
        container_run_uid=resolved.container_run_uid,
        container_run_gid=resolved.container_run_gid,
        agent_turn_timeout_seconds=resolved.sticky_turn_timeout_seconds,
        agent_max_turns=resolved.sticky_max_turns,
        container_hardening_enabled=resolved.container_hardening_enabled,
        container_cap_drop_all=resolved.container_cap_drop_all,
        container_read_only_rootfs=resolved.container_read_only_rootfs,
        container_no_new_privileges=resolved.container_no_new_privileges,
        container_pids_limit=resolved.container_pids_limit,
        container_memory_limit=resolved.container_memory_limit,
        container_tmpfs_mounts=resolved.container_tmpfs_mounts,
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
