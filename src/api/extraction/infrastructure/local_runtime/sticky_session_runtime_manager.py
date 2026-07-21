"""Dispatches sticky GMA session Sandbox lifecycle to a user's local agent.

See specs/extraction/local-sandbox-execution.spec.md, "Local Runtime Work
Request Lifecycle" and "Unchanged Sandbox Lifecycle Semantics". This adapter
never touches `sandbox.py`/`policy.py`/`gateway.py` directly -- it enqueues
`local_runtime_work_requests` rows that a local agent (specs "Chat Turn
Relay Through the Local Agent" companion: the agent process itself) claims
and executes using those same OpenShell modules, unchanged, on the user's
own machine.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from extraction.domain.local_runtime import (
    LocalRuntimeWorkKind,
    LocalRuntimeWorkRequest,
)
from extraction.infrastructure.local_runtime.dispatch import (
    LocalAgentUnavailableError,
    dispatch_and_await_completion,
)
from extraction.infrastructure.local_runtime.session_bridge import (
    run_with_local_runtime_repository,
)
from extraction.infrastructure.repositories.local_runtime_repository import (
    LocalRuntimeRepository,
)
from extraction.ports.runtime import (
    IStickySessionRuntimeManager,
    StickySessionRuntimeBootstrap,
    StickySessionRuntimeLease,
)

logger = logging.getLogger(__name__)

__all__ = ["LocalAgentUnavailableError", "LocalStickySessionRuntimeManager"]


def _run_best_effort(coro: Any, *, background_tasks: set[asyncio.Task]) -> None:
    """Run a fire-and-forget coroutine whether or not a loop is running.

    `terminate_runtime`/`cleanup_expired` are called two different ways by
    this codebase: directly from an already-`async def` method's running
    event loop (`agent_session_service.py`), and never (for this adapter)
    via `asyncio.to_thread`. `asyncio.run()` would raise
    "cannot be called from a running event loop" in the first case, so we
    detect which situation we're in: schedule a tracked background task if a
    loop is already running (never blocking that loop), otherwise fall back
    to `asyncio.run()` for the to_thread/plain-thread case.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    task = loop.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


#: Local execution always requests hard Landlock enforcement, regardless of
#: the soft/hard_requirement setting used for hosted OpenShell execution
#: (specs/extraction/local-sandbox-execution.spec.md, "Local Execution Always
#: Requests Hard Landlock Enforcement").
_LOCAL_POLICY_ENFORCEMENT = "hard_requirement"


class LocalStickySessionRuntimeManager(IStickySessionRuntimeManager):
    """Sticky runtime manager backed by a user's local agent, not a local container.

    Caches resolved leases in memory (mirroring `InMemoryStickySessionRuntimeManager`)
    since the actual Sandbox process lives on the user's machine, not this one --
    there is nothing further to look up beyond "did dispatch succeed and when
    does this lease logically expire".
    """

    def __init__(
        self,
        *,
        sticky_image: str = "kartograph-agent-runtime:dev",
        session_ttl: timedelta = timedelta(minutes=60),
        dispatch_timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 1.5,
        presence_timeout_seconds: float = 45.0,
        vertex_project_id: str = "",
        vertex_region: str = "us-east5",
        vertex_enabled: bool = False,
    ) -> None:
        self._sticky_image = sticky_image
        self._session_ttl = session_ttl
        self._dispatch_timeout_seconds = dispatch_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._presence_timeout_seconds = presence_timeout_seconds
        self._vertex_project_id = vertex_project_id
        self._vertex_region = vertex_region
        self._vertex_enabled = vertex_enabled
        self._leases: dict[str, StickySessionRuntimeLease] = {}
        self._background_tasks: set[asyncio.Task] = set()

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

        lease = asyncio.run(
            self._dispatch_sandbox_start(
                session_id=session_id,
                user_id=user_id,
                knowledge_graph_id=knowledge_graph_id,
                mode=mode,
                now=now,
                bootstrap=bootstrap,
            )
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
        self.terminate_runtime(
            session_id=session_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )
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
        lease = self._leases.pop(session_id, None)
        if lease is None:
            return
        # Best-effort: enqueue and move on. The local agent will tear down its
        # own Sandbox on claim; we don't block the caller waiting for that.
        _run_best_effort(
            self._enqueue_sandbox_stop(
                session_id=session_id,
                user_id=user_id,
                knowledge_graph_id=knowledge_graph_id,
                container_id=lease.container_id,
            ),
            background_tasks=self._background_tasks,
        )

    async def _enqueue_sandbox_stop(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        container_id: str,
    ) -> None:
        try:
            await self._enqueue(
                user_id=user_id,
                tenant_id="",
                knowledge_graph_id=knowledge_graph_id,
                kind=LocalRuntimeWorkKind.SANDBOX_STOP,
                session_id=session_id,
                payload={"container_id": container_id},
            )
        except Exception:  # noqa: BLE001 - best-effort teardown, never block callers
            logger.warning(
                "Failed to enqueue sandbox_stop for session %s; local agent "
                "will still reclaim resources on its next reconciliation.",
                session_id,
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
            self.terminate_runtime(
                session_id=session_id,
                user_id=lease.user_id,
                knowledge_graph_id=lease.knowledge_graph_id,
                mode=lease.mode,
            )
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

    async def _enqueue(
        self,
        *,
        user_id: str,
        tenant_id: str,
        knowledge_graph_id: str,
        kind: LocalRuntimeWorkKind,
        session_id: str,
        payload: dict[str, Any],
    ) -> LocalRuntimeWorkRequest:
        async def _do(repo: LocalRuntimeRepository, session: AsyncSession):  # type: ignore[no-untyped-def]
            request = await repo.enqueue_work_request(
                tenant_id=tenant_id,
                user_id=user_id,
                knowledge_graph_id=knowledge_graph_id,
                kind=kind,
                session_id=session_id,
                payload=payload,
            )
            await session.commit()
            return request

        return await run_with_local_runtime_repository(_do)

    def _build_sandbox_start_payload(
        self,
        *,
        mode: str,
        bootstrap: StickySessionRuntimeBootstrap | None,
    ) -> dict[str, Any]:
        """Everything a local agent needs to start the same Sandbox hosted
        execution would have started, short of the JobPackage contents
        themselves (those live at ``host_session_work_dir`` on the API's own
        host and are not meaningful on a remote machine; materializing them
        locally is the local agent's own responsibility -- see
        specs/extraction/local-sandbox-execution.spec.md, "Unchanged Sandbox
        Lifecycle Semantics").
        """
        # The Vertex access token itself is not embedded here: the local agent
        # requests it from the hosted API's vertex-token endpoint after
        # claiming this request (specs "Downscoped, Short-Lived Vertex
        # Credential Injection"), keeping the token's minted-to-used window as
        # short as possible rather than letting it sit at rest in this row.
        payload: dict[str, Any] = {
            "mode": mode,
            "sticky_image": self._sticky_image,
            "policy_enforcement": _LOCAL_POLICY_ENFORCEMENT,
            "vertex_enabled": self._vertex_enabled,
            "vertex_project_id": self._vertex_project_id,
            "vertex_region": self._vertex_region,
        }
        if bootstrap is not None:
            payload.update(
                {
                    "tenant_id": bootstrap.tenant_id,
                    "ui_mode": bootstrap.ui_mode,
                    "api_base_url": bootstrap.api_base_url,
                    "workload_token": bootstrap.credentials.token,
                    "workload_token_expires_at": bootstrap.credentials.expires_at.isoformat(),
                    "workload_token_scopes": list(bootstrap.credentials.scopes),
                }
            )
        return payload

    async def _dispatch_sandbox_start(
        self,
        *,
        session_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: str,
        now: datetime,
        bootstrap: StickySessionRuntimeBootstrap | None,
    ) -> StickySessionRuntimeLease:
        tenant_id = bootstrap.tenant_id if bootstrap is not None else ""

        completed = await dispatch_and_await_completion(
            tenant_id=tenant_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            kind=LocalRuntimeWorkKind.SANDBOX_START,
            session_id=session_id,
            payload=self._build_sandbox_start_payload(mode=mode, bootstrap=bootstrap),
            dispatch_timeout_seconds=self._dispatch_timeout_seconds,
            poll_interval_seconds=self._poll_interval_seconds,
            presence_timeout_seconds=self._presence_timeout_seconds,
            timeout_message=(
                "Timed out waiting for the local agent to claim and start the "
                "Sandbox. Ensure your local agent is running and connected."
            ),
            default_failure_message="Local agent failed to start the Sandbox.",
        )
        result = completed.result or {}
        container_id = str(result.get("container_id") or completed.id)
        return StickySessionRuntimeLease(
            session_id=session_id,
            container_id=container_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            status="active",
            last_activity_at=now,
            expires_at=now + self._session_ttl,
            runtime_base_url=f"local-agent://{completed.id}",
        )
