"""Container-backed extraction workload runtime adapters."""

from __future__ import annotations

import re
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
from shared_kernel.container_runtime.ports import ContainerRunSpec, IContainerRuntime

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _sanitize_container_name(prefix: str, identifier: str) -> str:
    cleaned = _CONTAINER_NAME_SAFE.sub("-", identifier).strip("-")
    name = f"{prefix}{cleaned}"
    return name[:63].rstrip("-_.") or f"{prefix}runtime"


class ContainerStickySessionRuntimeManager(IStickySessionRuntimeManager):
    """Sticky runtime manager backed by real container lifecycle operations."""

    def __init__(
        self,
        *,
        container_runtime: IContainerRuntime,
        sticky_image: str,
        sticky_command: tuple[str, ...],
        session_ttl: timedelta = timedelta(minutes=30),
    ) -> None:
        self._container_runtime = container_runtime
        self._sticky_image = sticky_image
        self._sticky_command = sticky_command
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
        if (
            existing is not None
            and existing.expires_at > now
            and self._container_runtime.is_running(existing.container_id)
        ):
            refreshed = replace(
                existing,
                last_activity_at=now,
                expires_at=now + self._session_ttl,
                status="active",
            )
            self._leases[session_id] = refreshed
            return refreshed

        if existing is not None:
            self._terminate_container(existing.container_id)

        lease = self._start_runtime(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            now=now,
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
        existing = self._leases.pop(session_id, None)
        if existing is not None:
            self._terminate_container(existing.container_id)
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
            self._terminate_container(lease.container_id)
            terminated.append(lease.container_id)
        return terminated

    def _start_runtime(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
        now: datetime,
    ) -> StickySessionRuntimeLease:
        container_name = _sanitize_container_name("kartograph-sticky-", session_id)
        launched = self._container_runtime.run(
            ContainerRunSpec(
                image=self._sticky_image,
                name=container_name,
                labels={
                    "kartograph.runtime.kind": "sticky",
                    "kartograph.session_id": session_id,
                    "kartograph.user_id": user_id,
                    "kartograph.knowledge_graph_id": knowledge_graph_id,
                    "kartograph.mode": mode,
                },
                command=self._sticky_command,
            )
        )
        return StickySessionRuntimeLease(
            session_id=session_id,
            container_id=launched.container_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            status="active",
            last_activity_at=now,
            expires_at=now + self._session_ttl,
        )

    def _terminate_container(self, container_id: str) -> None:
        if self._container_runtime.is_running(container_id):
            self._container_runtime.stop(container_id)
        self._container_runtime.remove(container_id, force=True)


class ContainerEphemeralExtractionWorkerLauncher(IEphemeralExtractionWorkerLauncher):
    """Ephemeral worker launcher backed by real container lifecycle operations."""

    def __init__(
        self,
        *,
        container_runtime: IContainerRuntime,
        worker_image: str,
        worker_command: tuple[str, ...],
    ) -> None:
        self._container_runtime = container_runtime
        self._worker_image = worker_image
        self._worker_command = worker_command
        self._active_workers: dict[str, tuple[EphemeralWorkerLaunchRequest, str]] = {}

    @property
    def active_worker_count(self) -> int:
        return len(self._active_workers)

    def worker_container_id(self, worker_id: str) -> str | None:
        worker = self._active_workers.get(worker_id)
        if worker is None:
            return None
        return worker[1]

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
        container_name = _sanitize_container_name("kartograph-worker-", worker_id)
        launched = self._container_runtime.run(
            ContainerRunSpec(
                image=self._worker_image,
                name=container_name,
                env={
                    "KARTOGRAPH_WORKLOAD_TOKEN": credentials.token,
                    "KARTOGRAPH_TENANT_ID": request.tenant_id,
                    "KARTOGRAPH_KNOWLEDGE_GRAPH_ID": request.knowledge_graph_id,
                    "KARTOGRAPH_SESSION_ID": request.session_id,
                    "KARTOGRAPH_SYNC_RUN_ID": request.sync_run_id,
                    "KARTOGRAPH_JOB_PACKAGE_ID": request.job_package_id,
                },
                labels={
                    "kartograph.runtime.kind": "ephemeral",
                    "kartograph.worker_id": worker_id,
                    "kartograph.session_id": request.session_id,
                    "kartograph.sync_run_id": request.sync_run_id,
                    "kartograph.job_package_id": request.job_package_id,
                },
                command=self._worker_command,
            )
        )
        self._active_workers[worker_id] = (request, launched.container_id)
        return EphemeralWorkerLaunchResult(
            worker_id=worker_id,
            status="running",
            credentials_expires_at=credentials.expires_at,
        )

    def complete_worker(self, worker_id: str) -> None:
        worker = self._active_workers.pop(worker_id, None)
        if worker is None:
            return
        container_id = worker[1]
        if self._container_runtime.is_running(container_id):
            self._container_runtime.stop(container_id)
        self._container_runtime.remove(container_id, force=True)
