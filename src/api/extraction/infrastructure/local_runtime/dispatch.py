"""Shared dispatch-and-await helper for local runtime work requests.

Both Sandbox lifecycle dispatch (`sticky_session_runtime_manager.py`) and
chat turn relay (`chat_agent.py`) need the same shape of interaction with a
user's local agent: fail fast if no agent is connected, enqueue a work
request, commit so the agent's own poll connection can see it, then poll
until the agent claims and completes (or fails) it, or the dispatch timeout
elapses. This module is the one place that lifecycle lives.

See specs/extraction/local-sandbox-execution.spec.md, "Local Runtime Work
Request Lifecycle".
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
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


class LocalAgentUnavailableError(RuntimeError):
    """No local agent has polled for this user recently enough to dispatch to."""


async def dispatch_and_await_completion(
    *,
    tenant_id: str,
    user_id: str,
    knowledge_graph_id: str,
    kind: LocalRuntimeWorkKind,
    payload: dict[str, Any],
    dispatch_timeout_seconds: float,
    poll_interval_seconds: float,
    presence_timeout_seconds: float,
    session_id: str | None = None,
    job_id: str | None = None,
    unavailable_message: str = (
        "No local agent is currently connected for this user. "
        "Start your local agent and try again."
    ),
    timeout_message: str = (
        "Timed out waiting for the local agent to claim and complete this "
        "request. Ensure your local agent is running and connected."
    ),
    default_failure_message: str = "Local agent reported failure with no reason given.",
) -> LocalRuntimeWorkRequest:
    """Enqueue one work request and block (this coroutine) until it settles.

    Raises `LocalAgentUnavailableError` immediately if no agent has polled
    within `presence_timeout_seconds`, `RuntimeError` if the agent reports
    failure, or `TimeoutError` if `dispatch_timeout_seconds` elapses first.
    """

    async def _run(  # type: ignore[no-untyped-def]
        repo: LocalRuntimeRepository, session: AsyncSession
    ) -> LocalRuntimeWorkRequest:
        now = datetime.now(UTC)
        presence = await repo.get_presence(user_id=user_id)
        if (
            presence is None
            or (now - presence.last_seen_at).total_seconds() > presence_timeout_seconds
        ):
            raise LocalAgentUnavailableError(unavailable_message)

        request = await repo.enqueue_work_request(
            tenant_id=tenant_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            kind=kind,
            session_id=session_id,
            job_id=job_id,
            payload=payload,
        )
        # Commit so the pending row is visible to the local agent's own
        # poll connection. Postgres READ COMMITTED gives each subsequent
        # statement in this same (still-open) transaction a fresh snapshot,
        # so no further commits are needed for the poll reads below to
        # observe the agent's claim/completion.
        await session.commit()

        deadline = asyncio.get_event_loop().time() + dispatch_timeout_seconds
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(poll_interval_seconds)
            current = await repo.get_by_id(request_id=request.id, user_id=user_id)
            if current is None:
                continue
            if current.status == LocalRuntimeWorkStatus.COMPLETED:
                return current
            if current.status == LocalRuntimeWorkStatus.FAILED:
                raise RuntimeError(current.failure_reason or default_failure_message)
        raise TimeoutError(timeout_message)

    return await run_with_local_runtime_repository(_run)
