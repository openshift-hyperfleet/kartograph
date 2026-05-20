"""In-memory runtime adapters for extraction session/workload execution."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from ulid import ULID

from extraction.ports.runtime import (
    EphemeralWorkerLaunchRequest,
    EphemeralWorkerLaunchResult,
    IEphemeralExtractionWorkerLauncher,
    IStickySessionRuntimeManager,
    ScopedWorkloadCredentials,
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
    ) -> StickySessionRuntimeLease:
        self._leases.pop(session_id, None)
        return self.get_or_start_runtime(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )

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


class ScopedWorkloadCredentialIssuer:
    """Issues short-lived tenant/KG scoped credentials for extraction workers."""

    def __init__(self, *, default_ttl: timedelta = timedelta(minutes=15)) -> None:
        self._default_ttl = default_ttl

    def issue(self, *, tenant_id: str, knowledge_graph_id: str) -> ScopedWorkloadCredentials:
        now = datetime.now(UTC)
        return ScopedWorkloadCredentials(
            token=str(ULID()),
            expires_at=now + self._default_ttl,
            scopes=(
                f"tenant:{tenant_id}",
                f"knowledge_graph:{knowledge_graph_id}",
                "workload:extraction",
            ),
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

