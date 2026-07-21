"""Integration tests for the local-runtime chat turn relay adapter.

Covers specs/extraction/local-sandbox-execution.spec.md, "Chat Turn Relay
Through the Local Agent" -- exercised end-to-end against the real database,
including a concurrent fake local agent claiming and completing dispatched
`chat_turn` work requests the same way a real local agent would from its
own connection.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from sqlalchemy import text

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.local_runtime import LocalRuntimeWorkKind, LocalRuntimeWorkStatus
from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode
from extraction.infrastructure.local_runtime.chat_agent import LocalStickyChatAgent
from extraction.infrastructure.local_runtime.dispatch import LocalAgentUnavailableError
from extraction.infrastructure.repositories.local_runtime_repository import (
    LocalRuntimeRepository,
)

pytestmark = pytest.mark.integration


def _agent(**overrides) -> LocalStickyChatAgent:
    defaults = dict(
        dispatch_timeout_seconds=6.0,
        poll_interval_seconds=0.3,
        presence_timeout_seconds=45.0,
    )
    defaults.update(overrides)
    return LocalStickyChatAgent(**defaults)


def _ready_session(*, user_id: str, knowledge_graph_id: str) -> ExtractionAgentSession:
    return ExtractionAgentSession(
        id=f"sess-{user_id}",
        user_id=user_id,
        knowledge_graph_id=knowledge_graph_id,
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        runtime_context={"sticky_runtime": {"phase": "ready"}},
    )


async def _fake_agent_completes(
    async_session, *, user_id: str, delay_seconds: float, events: list[dict]
) -> None:
    await asyncio.sleep(delay_seconds)
    repo = LocalRuntimeRepository(async_session)
    claimed = await repo.claim_next_pending(user_id=user_id)
    assert claimed is not None
    await repo.mark_completed(
        request_id=claimed.id, user_id=user_id, result={"events": events}
    )
    await async_session.commit()


async def _fake_agent_fails(
    async_session, *, user_id: str, delay_seconds: float, reason: str
) -> None:
    await asyncio.sleep(delay_seconds)
    repo = LocalRuntimeRepository(async_session)
    claimed = await repo.claim_next_pending(user_id=user_id)
    assert claimed is not None
    await repo.mark_failed(
        request_id=claimed.id, user_id=user_id, failure_reason=reason
    )
    await async_session.commit()


@pytest.mark.asyncio
async def test_runtime_not_ready_short_circuits_without_dispatch(
    async_session, clean_local_runtime_data
) -> None:
    agent = _agent()
    session = ExtractionAgentSession(
        id="sess-not-ready",
        user_id="user-cr-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        runtime_context={},
    )

    events = [
        event
        async for event in agent.stream_turn(
            session=session,
            user_message="hello",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            tenant_id="tenant-1",
        )
    ]

    assert len(events) == 1
    assert events[0]["type"] == "done"
    assert events[0]["ok"] is False
    assert events[0]["error"]["code"] == "RUNTIME_UNAVAILABLE"

    count = await async_session.execute(
        text("SELECT count(*) FROM local_runtime_work_requests")
    )
    assert count.scalar_one() == 0


@pytest.mark.asyncio
async def test_no_local_agent_connected_fails_fast(
    async_session, clean_local_runtime_data
) -> None:
    agent = _agent(dispatch_timeout_seconds=30.0)
    session = _ready_session(user_id="user-cr-absent", knowledge_graph_id="kg-1")
    started = time.monotonic()

    events = [
        event
        async for event in agent.stream_turn(
            session=session,
            user_message="hello",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            tenant_id="tenant-1",
        )
    ]

    elapsed = time.monotonic() - started
    assert elapsed < 5.0, "must fail immediately, not wait out the dispatch timeout"
    assert events[0]["error"]["code"] == "LOCAL_AGENT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_dispatches_chat_turn_and_replays_buffered_events(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-cr-2", tenant_id="tenant-1")
    await async_session.commit()

    agent = _agent()
    session = _ready_session(user_id="user-cr-2", knowledge_graph_id="kg-1")
    buffered_events = [
        {"type": "thinking", "recent": ["Contacting Graph Management Assistant…"]},
        {"type": "done", "ok": True, "reply": "Hello from the local Sandbox"},
    ]
    agent_task = asyncio.create_task(
        _fake_agent_completes(
            async_session,
            user_id="user-cr-2",
            delay_seconds=0.5,
            events=buffered_events,
        )
    )

    events = [
        event
        async for event in agent.stream_turn(
            session=session,
            user_message="hello",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            tenant_id="tenant-1",
        )
    ]
    await agent_task

    assert events == buffered_events

    rows = await async_session.execute(
        text(
            "SELECT kind, status, tenant_id FROM local_runtime_work_requests "
            "WHERE session_id = :sid"
        ),
        {"sid": session.id},
    )
    kind, status, tenant_id = rows.one()
    assert kind == LocalRuntimeWorkKind.CHAT_TURN.value
    assert status == LocalRuntimeWorkStatus.COMPLETED.value
    assert tenant_id == "tenant-1"


@pytest.mark.asyncio
async def test_agent_failure_surfaces_as_done_error_event(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-cr-3", tenant_id="tenant-1")
    await async_session.commit()

    agent = _agent()
    session = _ready_session(user_id="user-cr-3", knowledge_graph_id="kg-1")
    agent_task = asyncio.create_task(
        _fake_agent_fails(
            async_session,
            user_id="user-cr-3",
            delay_seconds=0.5,
            reason="Sandbox exec failed",
        )
    )

    events = [
        event
        async for event in agent.stream_turn(
            session=session,
            user_message="hello",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            tenant_id="tenant-1",
        )
    ]
    await agent_task

    assert len(events) == 1
    assert events[0]["type"] == "done"
    assert events[0]["ok"] is False
    assert events[0]["error"]["code"] == "LOCAL_AGENT_CHAT_TURN_FAILED"
    assert "Sandbox exec failed" in events[0]["error"]["message"]


@pytest.mark.asyncio
async def test_dispatch_timeout_surfaces_as_done_error_event(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-cr-4", tenant_id="tenant-1")
    await async_session.commit()

    agent = _agent(dispatch_timeout_seconds=1.0, poll_interval_seconds=0.2)
    session = _ready_session(user_id="user-cr-4", knowledge_graph_id="kg-1")

    events = [
        event
        async for event in agent.stream_turn(
            session=session,
            user_message="hello",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            tenant_id="tenant-1",
        )
    ]

    assert events[0]["error"]["code"] == "LOCAL_AGENT_TIMEOUT"


@pytest.mark.asyncio
async def test_missing_events_in_result_surfaces_invalid_result_error(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-cr-5", tenant_id="tenant-1")
    await async_session.commit()

    agent = _agent()
    session = _ready_session(user_id="user-cr-5", knowledge_graph_id="kg-1")
    agent_task = asyncio.create_task(
        _fake_agent_completes(
            async_session, user_id="user-cr-5", delay_seconds=0.5, events=[]
        )
    )

    events = [
        event
        async for event in agent.stream_turn(
            session=session,
            user_message="hello",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            tenant_id="tenant-1",
        )
    ]
    await agent_task

    assert events[0]["error"]["code"] == "LOCAL_AGENT_INVALID_RESULT"


def test_local_agent_unavailable_error_is_importable_from_dispatch_module() -> None:
    # LocalAgentUnavailableError moved to dispatch.py in the shared refactor;
    # sticky_session_runtime_manager.py re-exports it for backward compatibility.
    assert issubclass(LocalAgentUnavailableError, RuntimeError)
