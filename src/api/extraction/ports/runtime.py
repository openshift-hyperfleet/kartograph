"""Runtime port contracts for extraction workload execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class StickySessionRuntimeLease:
    """Represents sticky runtime assignment for an active chat session."""

    session_id: str
    container_id: str
    user_id: str
    knowledge_graph_id: str
    mode: str
    status: str
    last_activity_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class ScopedWorkloadCredentials:
    """Short-lived credentials issued for one extraction workload scope."""

    token: str
    expires_at: datetime
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class EphemeralWorkerLaunchRequest:
    """Launch payload for an ephemeral extraction worker."""

    tenant_id: str
    knowledge_graph_id: str
    session_id: str
    sync_run_id: str
    job_package_id: str


@dataclass(frozen=True)
class EphemeralWorkerLaunchResult:
    """Safe result returned after worker launch."""

    worker_id: str
    status: str
    credentials_expires_at: datetime


class IStickySessionRuntimeManager(Protocol):
    """Manages sticky chat runtime containers for active sessions."""

    def get_or_start_runtime(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
    ) -> StickySessionRuntimeLease:
        """Return current runtime lease or start a new sticky runtime."""
        ...

    def reset_runtime(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
    ) -> StickySessionRuntimeLease:
        """Terminate existing runtime for session and start a clean one."""
        ...

    def cleanup_expired(self, *, now: datetime) -> list[str]:
        """Terminate and remove expired sticky runtimes; return container IDs."""
        ...


class IEphemeralExtractionWorkerLauncher(Protocol):
    """Launches short-lived extraction workers with scoped credentials."""

    def launch(
        self,
        *,
        request: EphemeralWorkerLaunchRequest,
        credentials: ScopedWorkloadCredentials,
    ) -> EphemeralWorkerLaunchResult:
        """Start ephemeral worker; must not expose credential material."""
        ...

    def complete_worker(self, worker_id: str) -> None:
        """Mark worker as completed and terminate runtime resources."""
        ...

