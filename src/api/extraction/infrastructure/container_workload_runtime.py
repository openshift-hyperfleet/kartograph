"""Container-backed extraction workload runtime adapters."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from ulid import ULID

from extraction.infrastructure.vertex_runtime_env import build_vertex_container_env
from extraction.ports.runtime import (
    EphemeralWorkerLaunchRequest,
    EphemeralWorkerLaunchResult,
    IEphemeralExtractionWorkerLauncher,
    IStickySessionRuntimeManager,
    ScopedWorkloadCredentials,
    StickySessionRuntimeBootstrap,
    StickySessionRuntimeLease,
)
from shared_kernel.container_runtime.ports import ContainerRunSpec, IContainerRuntime

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _sanitize_container_name(prefix: str, identifier: str) -> str:
    cleaned = _CONTAINER_NAME_SAFE.sub("-", identifier).strip("-")
    name = f"{prefix}{cleaned}"
    return name[:63].rstrip("-_.") or f"{prefix}runtime"


_GCLOUD_ADC_FILENAME = "application_default_credentials.json"


def _gcloud_adc_env(*, container_config_path: str) -> dict[str, str]:
    base = container_config_path.rstrip("/")
    return {
        "CLOUDSDK_CONFIG": base,
        "GOOGLE_APPLICATION_CREDENTIALS": f"{base}/{_GCLOUD_ADC_FILENAME}",
        "HOME": "/tmp",
    }


class ContainerStickySessionRuntimeManager(IStickySessionRuntimeManager):
    """Sticky runtime manager backed by real container lifecycle operations."""

    def __init__(
        self,
        *,
        container_runtime: IContainerRuntime,
        sticky_image: str,
        sticky_command: tuple[str, ...],
        session_ttl: timedelta = timedelta(minutes=30),
        container_network: str | None = None,
        sticky_service_port: int = 8787,
        container_skills_mount: str = "/app/skills",
        container_work_mount: str = "/workspace",
        vertex_project_id: str = "",
        vertex_region: str = "us-east5",
        vertex_enabled: bool = False,
        gcloud_config_mount: str | None = None,
        gcloud_config_container_path: str = "/gcloud/config",
        container_run_uid: int | None = None,
        container_run_gid: int | None = None,
        agent_turn_timeout_seconds: float = 600.0,
        agent_max_turns: int = 500,
    ) -> None:
        self._container_runtime = container_runtime
        self._sticky_image = sticky_image
        self._sticky_command = sticky_command
        self._session_ttl = session_ttl
        self._container_network = container_network
        self._sticky_service_port = sticky_service_port
        self._container_skills_mount = container_skills_mount
        self._container_work_mount = container_work_mount
        self._vertex_project_id = vertex_project_id
        self._vertex_region = vertex_region
        self._vertex_enabled = vertex_enabled
        self._gcloud_config_mount = gcloud_config_mount
        self._gcloud_config_container_path = gcloud_config_container_path
        self._container_run_uid = container_run_uid
        self._container_run_gid = container_run_gid
        self._agent_turn_timeout_seconds = agent_turn_timeout_seconds
        self._agent_max_turns = agent_max_turns
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

        adopted = self._adopt_running_container_if_present(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            now=now,
            container_id_hint=None,
        )
        if adopted is not None:
            self._leases[session_id] = adopted
            return adopted

        if existing is not None:
            self._terminate_container(existing.container_id)

        lease = self._start_runtime(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            now=now,
            bootstrap=bootstrap,
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
        existing = self._leases.pop(session_id, None)
        if existing is not None:
            self._terminate_container(existing.container_id)
        return self.get_or_start_runtime(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            bootstrap=bootstrap,
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
        if (
            lease is not None
            and lease.expires_at > now
            and self._container_runtime.is_running(lease.container_id)
        ):
            refreshed = replace(
                lease,
                last_activity_at=now,
                expires_at=now + self._session_ttl,
                status="active",
            )
            self._leases[session_id] = refreshed
            return refreshed

        adopt_user_id = lease.user_id if lease is not None else user_id
        adopt_kg_id = lease.knowledge_graph_id if lease is not None else knowledge_graph_id
        adopt_mode = lease.mode if lease is not None else mode
        hints = [container_id] if container_id else []
        container_name = _sanitize_container_name("kartograph-sticky-", session_id)
        named_id = self._container_runtime.container_id_for_name(container_name)
        if named_id is not None:
            hints.append(named_id)

        for hint in hints:
            if not hint or not self._container_runtime.is_running(hint):
                continue
            adopted = self._adopt_running_container_if_present(
                session_id=session_id,
                user_id=adopt_user_id,
                knowledge_graph_id=adopt_kg_id,
                mode=adopt_mode,
                now=now,
                container_id_hint=hint,
            )
            if adopted is not None:
                self._leases[session_id] = adopted
                return adopted
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

    def _adopt_running_container_if_present(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
        now: datetime,
        container_id_hint: str | None,
    ) -> StickySessionRuntimeLease | None:
        container_name = _sanitize_container_name("kartograph-sticky-", session_id)
        container_id = container_id_hint or self._container_runtime.container_id_for_name(
            container_name
        )
        if container_id is None:
            return None
        runtime_base_url = f"http://{container_name}:{self._sticky_service_port}"
        return StickySessionRuntimeLease(
            session_id=session_id,
            container_id=container_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            status="active",
            last_activity_at=now,
            expires_at=now + self._session_ttl,
            runtime_base_url=runtime_base_url,
        )

    def _start_runtime(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
        now: datetime,
        bootstrap: StickySessionRuntimeBootstrap | None,
    ) -> StickySessionRuntimeLease:
        container_name = _sanitize_container_name("kartograph-sticky-", session_id)
        env: dict[str, str] = {
            "KARTOGRAPH_SESSION_ID": session_id,
            "KARTOGRAPH_KNOWLEDGE_GRAPH_ID": knowledge_graph_id,
            "KARTOGRAPH_USER_ID": user_id,
            "KARTOGRAPH_SESSION_MODE": mode,
            "KARTOGRAPH_SKILLS_DIR": self._container_skills_mount,
            "KARTOGRAPH_WORKSPACE_DIR": self._container_work_mount,
            "KARTOGRAPH_AGENT_TURN_TIMEOUT_SECONDS": str(int(self._agent_turn_timeout_seconds)),
            "KARTOGRAPH_AGENT_MAX_TURNS": str(int(self._agent_max_turns)),
        }
        binds: list[str] = []
        if bootstrap is not None:
            required_scopes = {
                f"tenant:{bootstrap.tenant_id}",
                f"knowledge_graph:{knowledge_graph_id}",
                "workload:chat",
            }
            if not required_scopes.issubset(set(bootstrap.credentials.scopes)):
                raise ValueError("sticky session credentials scope is invalid")
            if bootstrap.credentials.expires_at <= datetime.now(UTC):
                raise ValueError("sticky session credentials are expired")
            env.update(
                {
                    "KARTOGRAPH_WORKLOAD_TOKEN": bootstrap.credentials.token,
                    "KARTOGRAPH_TENANT_ID": bootstrap.tenant_id,
                    "KARTOGRAPH_API_BASE_URL": bootstrap.api_base_url,
                }
            )
            binds.extend(
                [
                    f"{bootstrap.host_skills_dir}:{self._container_skills_mount}:ro",
                    f"{bootstrap.host_session_work_dir}:{self._container_work_mount}:ro",
                ]
            )

        if self._vertex_enabled:
            env.update(
                build_vertex_container_env(
                    project_id=self._vertex_project_id,
                    region=self._vertex_region,
                )
            )
        if self._gcloud_config_mount:
            container_gcloud = self._gcloud_config_container_path.rstrip("/")
            binds.append(f"{self._gcloud_config_mount}:{container_gcloud}:ro")
            env.update(_gcloud_adc_env(container_config_path=container_gcloud))

        container_user: str | None = None
        if self._container_run_uid is not None and self._container_run_gid is not None:
            container_user = f"{self._container_run_uid}:{self._container_run_gid}"

        launched = self._container_runtime.run(
            ContainerRunSpec(
                image=self._sticky_image,
                name=container_name,
                env=env,
                binds=tuple(binds),
                network=self._container_network,
                user=container_user,
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
        runtime_base_url = f"http://{container_name}:{self._sticky_service_port}"
        return StickySessionRuntimeLease(
            session_id=session_id,
            container_id=launched.container_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            status="active",
            last_activity_at=now,
            expires_at=now + self._session_ttl,
            runtime_base_url=runtime_base_url,
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
