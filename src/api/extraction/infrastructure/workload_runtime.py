"""In-memory runtime adapters for extraction session/workload execution."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from ulid import ULID

from extraction.infrastructure.workload_credential_issuer import ScopedWorkloadCredentialIssuer
from extraction.ports.runtime import (
    EphemeralWorkerLaunchRequest,
    EphemeralWorkerLaunchResult,
    IEphemeralExtractionWorkerLauncher,
    IStickySessionRuntimeManager,
    ScopedWorkloadCredentials,
    StickySessionRuntimeBootstrap,
    StickySessionRuntimeLease,
)


class InMemoryStickySessionRuntimeManager(IStickySessionRuntimeManager):
    """Sticky runtime manager with session reuse + timeout cleanup semantics."""

    def __init__(self, *, session_ttl: timedelta = timedelta(minutes=30)) -> None:
        self._session_ttl = session_ttl
        self._leases: dict[str, StickySessionRuntimeLease] = {}

    def get_or_start_runtime(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
        bootstrap: StickySessionRuntimeBootstrap | None = None,
    ) -> StickySessionRuntimeLease:
        now = datetime.now(UTC)
        existing = self._leases.get(session_id)
        if existing is not None and existing.expires_at > now:
            refreshed = replace(
                existing,
                last_activity_at=now,
                expires_at=now + self._session_ttl,
                status="active",
            )
            self._leases[session_id] = refreshed
            return refreshed

        lease = StickySessionRuntimeLease(
            session_id=session_id,
            container_id=str(ULID()),
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            status="active",
            last_activity_at=now,
            expires_at=now + self._session_ttl,
            runtime_base_url="memory://sticky-runtime",
        )
        self._leases[session_id] = lease
        return lease

    def reset_runtime(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
        bootstrap: StickySessionRuntimeBootstrap | None = None,
    ) -> StickySessionRuntimeLease:
        self._leases.pop(session_id, None)
        return self.get_or_start_runtime(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )

    def terminate_runtime(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
    ) -> None:
        self._leases.pop(session_id, None)

    def cleanup_expired(self, *, now: datetime) -> list[str]:
        expired_sessions = [
            session_id
            for session_id, lease in self._leases.items()
            if lease.expires_at <= now
        ]
        terminated: list[str] = []
        for session_id in expired_sessions:
            lease = self._leases.pop(session_id)
            terminated.append(lease.container_id)
        return terminated

    def try_resolve_active_lease(
        self,
        *,
        session_id: str,
        user_id: str = "",
        knowledge_graph_id: str = "",
        mode: str = "",
        container_id: str | None = None,
    ) -> StickySessionRuntimeLease | None:
        now = datetime.now(UTC)
        lease = self._leases.get(session_id)
        if lease is not None and lease.expires_at > now:
            refreshed = replace(
                lease,
                last_activity_at=now,
                expires_at=now + self._session_ttl,
                status="active",
            )
            self._leases[session_id] = refreshed
            return refreshed
        return None

    def is_runtime_active(
        self,
        *,
        session_id: str,
        container_id: str | None = None,
        user_id: str = "",
        knowledge_graph_id: str = "",
        mode: str = "",
    ) -> bool:
        return (
            self.try_resolve_active_lease(
                session_id=session_id,
                container_id=container_id,
                user_id=user_id,
                knowledge_graph_id=knowledge_graph_id,
                mode=mode,
            )
            is not None
        )


class InMemoryEphemeralExtractionWorkerLauncher(IEphemeralExtractionWorkerLauncher):
    """Ephemeral worker launcher that validates scope and tracks active workers."""

    def __init__(self) -> None:
        self._active_workers: dict[str, EphemeralWorkerLaunchRequest] = {}

    @property
    def active_worker_count(self) -> int:
        return len(self._active_workers)

    def launch(
        self,
        *,
        request: EphemeralWorkerLaunchRequest,
        credentials: ScopedWorkloadCredentials,
    ) -> EphemeralWorkerLaunchResult:
        required_scopes = {
            f"tenant:{request.tenant_id}",
            f"knowledge_graph:{request.knowledge_graph_id}",
            "workload:extraction",
        }
        available_scopes = set(credentials.scopes)
        if not required_scopes.issubset(available_scopes):
            raise ValueError("credentials scope does not satisfy workload requirements")
        if credentials.expires_at <= datetime.now(UTC):
            raise ValueError("credentials are expired")

        worker_id = str(ULID())
        self._active_workers[worker_id] = request
        return EphemeralWorkerLaunchResult(
            worker_id=worker_id,
            status="running",
            credentials_expires_at=credentials.expires_at,
        )

    def complete_worker(self, worker_id: str) -> None:
        self._active_workers.pop(worker_id, None)

