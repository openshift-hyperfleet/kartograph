"""Integration tests for the local-runtime sticky session manager adapter.

Covers specs/extraction/local-sandbox-execution.spec.md requirements:
"Local Execution Mode Selection", "Unchanged Sandbox Lifecycle Semantics",
and the "No local agent has ever polled" / "Claim by polling agent"
scenarios, exercised end-to-end against the real database -- including a
concurrent fake local agent claiming and completing dispatched work, the
same way a real local agent would from its own connection.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from sqlalchemy import text

from extraction.domain.local_runtime import LocalRuntimeWorkKind, LocalRuntimeWorkStatus
from extraction.infrastructure.local_runtime.sticky_session_runtime_manager import (
    LocalAgentUnavailableError,
    LocalStickySessionRuntimeManager,
)
from extraction.infrastructure.repositories.local_runtime_repository import (
    LocalRuntimeRepository,
)
from extraction.ports.runtime import (
    ScopedWorkloadCredentials,
    StickySessionRuntimeBootstrap,
)
from datetime import UTC, datetime, timedelta

pytestmark = pytest.mark.integration


def _manager(**overrides) -> LocalStickySessionRuntimeManager:
    defaults = dict(
        dispatch_timeout_seconds=6.0,
        poll_interval_seconds=0.3,
        presence_timeout_seconds=45.0,
    )
    defaults.update(overrides)
    return LocalStickySessionRuntimeManager(**defaults)


async def _fake_agent_completes(
    async_session, *, user_id: str, delay_seconds: float, result: dict
) -> None:
    """Simulate a local agent claiming and completing the next pending request."""
    await asyncio.sleep(delay_seconds)
    repo = LocalRuntimeRepository(async_session)
    claimed = await repo.claim_next_pending(user_id=user_id)
    assert claimed is not None
    await repo.mark_completed(request_id=claimed.id, user_id=user_id, result=result)
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
async def test_no_local_agent_connected_fails_fast(
    async_session, clean_local_runtime_data
) -> None:
    manager = _manager(dispatch_timeout_seconds=30.0)
    started = time.monotonic()

    with pytest.raises(LocalAgentUnavailableError):
        await asyncio.to_thread(
            manager.get_or_start_runtime,
            session_id="sess-no-agent",
            user_id="user-absent",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )

    elapsed = time.monotonic() - started
    assert elapsed < 5.0, "must fail immediately, not wait out the dispatch timeout"


@pytest.mark.asyncio
async def test_dispatches_sandbox_start_and_returns_lease_once_agent_completes(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-1", tenant_id="tenant-1")
    await async_session.commit()

    manager = _manager()
    agent_task = asyncio.create_task(
        _fake_agent_completes(
            async_session,
            user_id="user-1",
            delay_seconds=0.5,
            result={"container_id": "sandbox-abc"},
        )
    )
    lease = await asyncio.to_thread(
        manager.get_or_start_runtime,
        session_id="sess-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode="schema_bootstrap",
    )
    await agent_task

    assert lease.container_id == "sandbox-abc"
    assert lease.status == "active"
    assert lease.runtime_base_url is not None
    assert lease.runtime_base_url.startswith("local-agent://")

    # Enqueued exactly one sandbox_start request, of the right kind.
    pending = await async_session.execute(
        text(
            "SELECT kind, status FROM local_runtime_work_requests WHERE session_id = :sid"
        ),
        {"sid": "sess-1"},
    )
    rows = pending.all()
    assert len(rows) == 1
    assert rows[0][0] == LocalRuntimeWorkKind.SANDBOX_START.value
    assert rows[0][1] == LocalRuntimeWorkStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_sandbox_start_payload_carries_bootstrap_fields_for_the_local_agent(
    async_session, clean_local_runtime_data
) -> None:
    """A local agent has no host-mounted access to the API's own filesystem,
    so the sandbox_start work request payload must carry everything it needs
    to reconstruct the same runtime env hosted execution would have built
    (sticky image, hard Landlock enforcement, tenant, and the workload
    credential) -- not just the bare session mode.
    """
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-6", tenant_id="tenant-1")
    await async_session.commit()

    manager = _manager(
        sticky_image="kartograph-agent-runtime:test",
        vertex_project_id="proj-123",
        vertex_region="us-east5",
        vertex_enabled=True,
    )
    bootstrap = StickySessionRuntimeBootstrap(
        tenant_id="tenant-1",
        credentials=ScopedWorkloadCredentials(
            token="workload-jwt-abc",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            scopes=("tenant:tenant-1", "knowledge_graph:kg-1"),
        ),
        host_session_work_dir="/tmp/should-not-matter",
        api_base_url="http://api:8000",
        ui_mode="schema_bootstrap",
    )
    agent_task = asyncio.create_task(
        _fake_agent_completes(
            async_session,
            user_id="user-6",
            delay_seconds=0.5,
            result={"container_id": "sandbox-bootstrap"},
        )
    )
    await asyncio.to_thread(
        manager.get_or_start_runtime,
        session_id="sess-6",
        user_id="user-6",
        knowledge_graph_id="kg-1",
        mode="schema_bootstrap",
        bootstrap=bootstrap,
    )
    await agent_task

    row = await async_session.execute(
        text(
            "SELECT payload, tenant_id FROM local_runtime_work_requests "
            "WHERE session_id = :sid"
        ),
        {"sid": "sess-6"},
    )
    payload, tenant_id = row.one()
    assert tenant_id == "tenant-1"
    assert payload["sticky_image"] == "kartograph-agent-runtime:test"
    assert payload["policy_enforcement"] == "hard_requirement"
    assert payload["tenant_id"] == "tenant-1"
    assert payload["ui_mode"] == "schema_bootstrap"
    assert payload["api_base_url"] == "http://api:8000"
    assert payload["workload_token"] == "workload-jwt-abc"
    assert "knowledge_graph:kg-1" in payload["workload_token_scopes"]
    assert payload["vertex_enabled"] is True
    assert payload["vertex_project_id"] == "proj-123"
    assert payload["vertex_region"] == "us-east5"


@pytest.mark.asyncio
async def test_work_request_failure_propagates_as_runtime_error(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-2", tenant_id="tenant-1")
    await async_session.commit()

    manager = _manager()
    agent_task = asyncio.create_task(
        _fake_agent_fails(
            async_session,
            user_id="user-2",
            delay_seconds=0.5,
            reason="Landlock enforcement unavailable",
        )
    )
    with pytest.raises(RuntimeError, match="Landlock enforcement unavailable"):
        await asyncio.to_thread(
            manager.get_or_start_runtime,
            session_id="sess-2",
            user_id="user-2",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )
    await agent_task


@pytest.mark.asyncio
async def test_dispatch_timeout_raises_when_never_claimed(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-3", tenant_id="tenant-1")
    await async_session.commit()

    manager = _manager(dispatch_timeout_seconds=1.0, poll_interval_seconds=0.2)
    with pytest.raises(TimeoutError):
        await asyncio.to_thread(
            manager.get_or_start_runtime,
            session_id="sess-3",
            user_id="user-3",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )


@pytest.mark.asyncio
async def test_active_lease_is_reused_without_new_dispatch(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-4", tenant_id="tenant-1")
    await async_session.commit()

    manager = _manager()
    agent_task = asyncio.create_task(
        _fake_agent_completes(
            async_session,
            user_id="user-4",
            delay_seconds=0.5,
            result={"container_id": "sandbox-reuse"},
        )
    )
    first = await asyncio.to_thread(
        manager.get_or_start_runtime,
        session_id="sess-4",
        user_id="user-4",
        knowledge_graph_id="kg-1",
        mode="schema_bootstrap",
    )
    await agent_task

    second = await asyncio.to_thread(
        manager.get_or_start_runtime,
        session_id="sess-4",
        user_id="user-4",
        knowledge_graph_id="kg-1",
        mode="schema_bootstrap",
    )
    assert second.container_id == first.container_id
    assert second.expires_at >= first.expires_at

    count = await async_session.execute(
        text(
            "SELECT count(*) FROM local_runtime_work_requests WHERE session_id = :sid"
        ),
        {"sid": "sess-4"},
    )
    assert count.scalar_one() == 1, "reused lease must not dispatch a second request"


@pytest.mark.asyncio
async def test_terminate_runtime_enqueues_sandbox_stop_and_drops_cached_lease(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    await repo.record_presence(user_id="user-5", tenant_id="tenant-1")
    await async_session.commit()

    manager = _manager()
    agent_task = asyncio.create_task(
        _fake_agent_completes(
            async_session,
            user_id="user-5",
            delay_seconds=0.5,
            result={"container_id": "sandbox-term"},
        )
    )
    await asyncio.to_thread(
        manager.get_or_start_runtime,
        session_id="sess-5",
        user_id="user-5",
        knowledge_graph_id="kg-1",
        mode="schema_bootstrap",
    )
    await agent_task

    manager.terminate_runtime(
        session_id="sess-5",
        user_id="user-5",
        knowledge_graph_id="kg-1",
        mode="schema_bootstrap",
    )
    # asyncio.run inside terminate_runtime needs a beat to land its commit.
    await asyncio.sleep(0.2)

    assert (
        manager.try_resolve_active_lease(session_id="sess-5", user_id="user-5") is None
    )
    stop_requests = await async_session.execute(
        text(
            "SELECT kind FROM local_runtime_work_requests "
            "WHERE session_id = :sid AND kind = :kind"
        ),
        {"sid": "sess-5", "kind": LocalRuntimeWorkKind.SANDBOX_STOP.value},
    )
    assert len(stop_requests.all()) == 1
