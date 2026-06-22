"""OpenShell-backed sticky session runtime manager."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from extraction.infrastructure.openshell import gateway as openshell_gateway
from extraction.infrastructure.openshell import sandbox as openshell_sandbox
from extraction.infrastructure.openshell.audit import LoggingOpenShellRuntimeProbe, OpenShellRuntimeProbe
from extraction.infrastructure.openshell.runtime_env import apply_openshell_gateway_env
from extraction.infrastructure.openshell.vertex_provider import ensure_vertex_provider
from extraction.infrastructure.runtime_session_auth import issue_runtime_auth_token
from extraction.infrastructure.workload_credential_issuer import WORKLOAD_SCOPE_WRITE
from extraction.infrastructure.vertex_runtime_env import (
    OPENSHELL_GCLOUD_CONTAINER_PATH,
    build_openshell_inference_container_env,
)
from extraction.ports.runtime import (
    IStickySessionRuntimeManager,
    StickySessionRuntimeBootstrap,
    StickySessionRuntimeLease,
)

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _sanitize_sandbox_name(session_id: str) -> str:
    return openshell_sandbox.sanitize_sandbox_name("kartograph-gma-", session_id)


def _forward_port(*, session_id: str, base: int) -> int:
    digest = sum(ord(char) for char in session_id)
    return base + (digest % 900)


def _api_host_from_base_url(api_base_url: str) -> str:
    parsed = urlparse(api_base_url)
    if parsed.hostname:
        port_suffix = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.hostname}{port_suffix}"
    return "api:8000"


class OpenShellStickySessionRuntimeManager(IStickySessionRuntimeManager):
    """Sticky runtime manager using OpenShell sandboxes with network policy."""

    def __init__(
        self,
        *,
        sticky_image: str,
        session_ttl: timedelta = timedelta(minutes=60),
        sticky_service_port: int = 8787,
        container_work_mount: str = "/sandbox",
        vertex_project_id: str = "",
        vertex_region: str = "us-east5",
        vertex_enabled: bool = False,
        gcloud_config_mount: str | None = None,
        gcloud_config_container_path: str = OPENSHELL_GCLOUD_CONTAINER_PATH,
        agent_turn_timeout_seconds: float = 1000.0,
        agent_max_turns: int = 500,
        api_base_url: str = "http://api:8000",
        gateway_name: str = "kartograph",
        gateway_url: str = "https://localhost:17670",
        provider_name: str = "kartograph-gma",
        runtime_host: str = "127.0.0.1",
        forward_port_base: int = 18787,
        policy_dir: str | None = None,
        policy_enforcement: str = "hard_requirement",
        probe: OpenShellRuntimeProbe | None = None,
    ) -> None:
        self._sticky_image = sticky_image
        self._session_ttl = session_ttl
        self._sticky_service_port = sticky_service_port
        self._container_work_mount = container_work_mount
        self._vertex_project_id = vertex_project_id
        self._vertex_region = vertex_region
        self._vertex_enabled = vertex_enabled
        self._gcloud_config_mount = gcloud_config_mount
        self._gcloud_config_container_path = gcloud_config_container_path.rstrip("/")
        self._agent_turn_timeout_seconds = agent_turn_timeout_seconds
        self._agent_max_turns = agent_max_turns
        self._api_base_url = api_base_url
        self._gateway_name = gateway_name
        self._gateway_url = gateway_url
        self._provider_name = provider_name
        self._runtime_host = runtime_host.rstrip("/")
        self._forward_port_base = forward_port_base
        self._policy_dir = policy_dir
        self._policy_enforcement = policy_enforcement
        self._probe = probe or LoggingOpenShellRuntimeProbe()
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
            if openshell_sandbox.sandbox_exists(existing.container_id):
                refreshed = replace(
                    existing,
                    last_activity_at=now,
                    expires_at=now + self._session_ttl,
                    status="active",
                )
                self._leases[session_id] = refreshed
                return refreshed

        if existing is not None:
            self._terminate_sandbox(existing)

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
            self._terminate_sandbox(existing)
        return self.get_or_start_runtime(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            bootstrap=bootstrap,
        )

    def terminate_runtime(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
    ) -> None:
        existing = self._leases.pop(session_id, None)
        if existing is not None:
            self._terminate_sandbox(existing)

    def cleanup_expired(self, *, now: datetime) -> list[str]:
        expired = [
            session_id
            for session_id, lease in self._leases.items()
            if lease.expires_at <= now
        ]
        terminated: list[str] = []
        for session_id in expired:
            lease = self._leases.pop(session_id)
            self._terminate_sandbox(lease)
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
        sandbox_name = container_id or _sanitize_sandbox_name(session_id)
        if lease is not None and lease.expires_at > now:
            if openshell_sandbox.sandbox_exists(lease.container_id):
                refreshed = replace(
                    lease,
                    last_activity_at=now,
                    expires_at=now + self._session_ttl,
                    status="active",
                )
                self._leases[session_id] = refreshed
                return refreshed
        if openshell_sandbox.sandbox_exists(sandbox_name):
            forward_port = _forward_port(session_id=session_id, base=self._forward_port_base)
            return StickySessionRuntimeLease(
                session_id=session_id,
                container_id=sandbox_name,
                user_id=user_id or (lease.user_id if lease else ""),
                knowledge_graph_id=knowledge_graph_id or (lease.knowledge_graph_id if lease else ""),
                mode=mode or (lease.mode if lease else ""),
                status="active",
                last_activity_at=now,
                expires_at=now + self._session_ttl,
                runtime_base_url=f"http://{self._runtime_host}:{forward_port}",
                runtime_auth_token=lease.runtime_auth_token if lease else None,
            )
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
        openshell_gateway.ensure_gateway_registered(
            gateway_name=self._gateway_name,
            gateway_url=self._gateway_url,
        )
        apply_openshell_gateway_env(
            gateway_name=self._gateway_name,
            gateway_url=self._gateway_url,
        )
        if self._vertex_enabled:
            ensure_vertex_provider(
                provider_name=self._provider_name,
                project_id=self._vertex_project_id,
                region=self._vertex_region,
                gcloud_config_mount=self._gcloud_config_mount,
                auth_mode="vertex",
            )
        sandbox_name = _sanitize_sandbox_name(session_id)
        forward_port = _forward_port(session_id=session_id, base=self._forward_port_base)
        runtime_auth_token = issue_runtime_auth_token()

        if bootstrap is not None:
            required_scopes = {
                f"tenant:{bootstrap.tenant_id}",
                f"knowledge_graph:{knowledge_graph_id}",
                WORKLOAD_SCOPE_WRITE,
            }
            if not required_scopes.issubset(set(bootstrap.credentials.scopes)):
                raise ValueError("sticky session credentials scope is invalid")
            if bootstrap.credentials.expires_at <= datetime.now(UTC):
                raise ValueError("sticky session credentials are expired")

        openshell_sandbox.delete_sandbox(sandbox_name)
        openshell_sandbox.create_sandbox(
            name=sandbox_name,
            image=self._sticky_image,
            provider_name=self._provider_name,
        )
        openshell_sandbox.emit_lifecycle(
            sandbox_name=sandbox_name,
            action="created",
            probe=self._probe,
            image=self._sticky_image,
            forward_port=forward_port,
            session_id=session_id,
        )

        if bootstrap is not None:
            openshell_sandbox.upload_directory_contents(
                sandbox_name=sandbox_name,
                local_dir=bootstrap.host_session_work_dir,
                dest=self._container_work_mount,
            )

        openshell_sandbox.apply_policy(
            sandbox_name=sandbox_name,
            ui_mode=(bootstrap.ui_mode if bootstrap else None) or mode,
            workload="gma",
            policy_dir=self._policy_dir,
            api_host=_api_host_from_base_url(bootstrap.api_base_url if bootstrap else self._api_base_url),
            vertex_region=self._vertex_region if self._vertex_enabled else None,
            policy_enforcement=self._policy_enforcement,
            probe=self._probe,
        )

        env = self._build_runtime_env(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            runtime_auth_token=runtime_auth_token,
            bootstrap=bootstrap,
        )
        openshell_sandbox.exec_background(
            sandbox_name=sandbox_name,
            env=env,
            command=(
                "/app/.venv/bin/python",
                "-m",
                "kartograph_agent_runtime",
            ),
        )
        openshell_sandbox.start_forward(
            sandbox_name=sandbox_name,
            port=forward_port,
            target_port=self._sticky_service_port,
        )
        openshell_sandbox.emit_lifecycle(
            sandbox_name=sandbox_name,
            action="started",
            probe=self._probe,
            forward_port=forward_port,
            session_id=session_id,
        )

        runtime_base_url = f"http://{self._runtime_host}:{forward_port}"
        return StickySessionRuntimeLease(
            session_id=session_id,
            container_id=sandbox_name,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            status="active",
            last_activity_at=now,
            expires_at=now + self._session_ttl,
            runtime_base_url=runtime_base_url,
            runtime_auth_token=runtime_auth_token,
        )

    def _build_runtime_env(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
        runtime_auth_token: str,
        bootstrap: StickySessionRuntimeBootstrap | None,
    ) -> dict[str, str]:
        env: dict[str, str] = {
            "KARTOGRAPH_SESSION_ID": session_id,
            "KARTOGRAPH_KNOWLEDGE_GRAPH_ID": knowledge_graph_id,
            "KARTOGRAPH_USER_ID": user_id,
            "KARTOGRAPH_SESSION_MODE": mode,
            "KARTOGRAPH_WORKSPACE_DIR": self._container_work_mount,
            "KARTOGRAPH_AGENT_TURN_TIMEOUT_SECONDS": str(int(self._agent_turn_timeout_seconds)),
            "KARTOGRAPH_AGENT_MAX_TURNS": str(int(self._agent_max_turns)),
            "KARTOGRAPH_RUNTIME_AUTH_TOKEN": runtime_auth_token,
        }
        if bootstrap is not None:
            env.update(
                {
                    "KARTOGRAPH_TENANT_ID": bootstrap.tenant_id,
                    "KARTOGRAPH_API_BASE_URL": bootstrap.api_base_url,
                }
            )
        if self._vertex_enabled:
            env.update(build_openshell_inference_container_env())
        return env

    def _terminate_sandbox(self, lease: StickySessionRuntimeLease) -> None:
        forward_port = _forward_port(session_id=lease.session_id, base=self._forward_port_base)
        openshell_sandbox.stop_forward(sandbox_name=lease.container_id, port=forward_port)
        openshell_sandbox.delete_sandbox(lease.container_id)
        openshell_sandbox.emit_lifecycle(
            sandbox_name=lease.container_id,
            action="deleted",
            probe=self._probe,
            session_id=lease.session_id,
        )
