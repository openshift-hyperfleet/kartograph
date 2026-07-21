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
    LocalRuntimeWorkStatus,
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


class LocalAgentUnavailableError(RuntimeError):
    """No local agent has polled for this user recently enough to dispatch to."""


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
        session_ttl: timedelta = timedelta(minutes=60),
        dispatch_timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 1.5,
        presence_timeout_seconds: float = 45.0,
    ) -> None:
        self._session_ttl = session_ttl
        self._dispatch_timeout_seconds = dispatch_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._presence_timeout_seconds = presence_timeout_seconds
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

        tenant_id = bootstrap.tenant_id if bootstrap is not None else ""
        lease = asyncio.run(
            self._dispatch_sandbox_start(
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                mode=mode,
                now=now,
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

    async def _dispatch_sandbox_start(
        self,
        *,
        session_id: str,
        user_id: str,
        tenant_id: str,
        knowledge_graph_id: str,
        mode: str,
        now: datetime,
    ) -> StickySessionRuntimeLease:
        async def _run(  # type: ignore[no-untyped-def]
            repo: LocalRuntimeRepository, session: AsyncSession
        ) -> LocalRuntimeWorkRequest:
            presence = await repo.get_presence(user_id=user_id)
            if presence is None or (
                now - presence.last_seen_at
            ).total_seconds() > self._presence_timeout_seconds:
                raise LocalAgentUnavailableError(
                    "No local agent is currently connected for this user. "
                    "Start your local agent and try again."
                )

            request = await repo.enqueue_work_request(
                tenant_id=tenant_id,
                user_id=user_id,
                knowledge_graph_id=knowledge_graph_id,
                kind=LocalRuntimeWorkKind.SANDBOX_START,
                session_id=session_id,
                payload={"mode": mode},
            )
            # Commit so the pending row is visible to the local agent's own
            # poll connection. Postgres READ COMMITTED gives each subsequent
            # statement in this same (still-open) transaction a fresh
            # snapshot, so no further commits are needed for the poll reads
            # below to observe the agent's claim/completion.
            await session.commit()

            deadline = asyncio.get_event_loop().time() + self._dispatch_timeout_seconds
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(self._poll_interval_seconds)
                current = await repo.get_by_id(request_id=request.id, user_id=user_id)
                if current is None:
                    continue
                if current.status == LocalRuntimeWorkStatus.COMPLETED:
                    return current
                if current.status == LocalRuntimeWorkStatus.FAILED:
                    raise RuntimeError(
                        current.failure_reason
                        or "Local agent failed to start the Sandbox."
                    )
            raise TimeoutError(
                "Timed out waiting for the local agent to claim and start the "
                "Sandbox. Ensure your local agent is running and connected."
            )

        completed = await run_with_local_runtime_repository(_run)
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
