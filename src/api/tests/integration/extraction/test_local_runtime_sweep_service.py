"""Integration tests for LocalRuntimeSweepService against the real database.

Covers specs/extraction/local-sandbox-execution.spec.md, "Claim timeout" and
"Heartbeat loss fails the claim".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from extraction.application.local_runtime_sweep_service import (
    LocalRuntimeSweepService,
)
from extraction.domain.local_runtime import LocalRuntimeWorkKind, LocalRuntimeWorkStatus
from extraction.infrastructure.repositories.local_runtime_repository import (
    LocalRuntimeRepository,
)

pytestmark = pytest.mark.integration


def _sweep_service(async_session, **overrides) -> LocalRuntimeSweepService:
    defaults = dict(
        claim_timeout=timedelta(seconds=60),
        heartbeat_timeout=timedelta(seconds=30),
    )
    defaults.update(overrides)
    return LocalRuntimeSweepService(
        repository=LocalRuntimeRepository(async_session), **defaults
    )


async def _backdate(
    async_session, *, request_id: str, column: str, when: datetime
) -> None:
    await async_session.execute(
        text(f"UPDATE local_runtime_work_requests SET {column} = :when WHERE id = :id"),  # noqa: S608
        {"when": when, "id": request_id},
    )
    await async_session.commit()


@pytest.mark.asyncio
async def test_sweep_fails_pending_request_past_claim_timeout(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-1",
    )
    await async_session.commit()
    await _backdate(
        async_session,
        request_id=request.id,
        column="created_at",
        when=datetime.now(UTC) - timedelta(minutes=5),
    )

    service = _sweep_service(async_session, claim_timeout=timedelta(seconds=30))
    claim_timeouts, heartbeat_timeouts = await service.sweep()

    assert claim_timeouts == 1
    assert heartbeat_timeouts == 0
    persisted = await repo.get_by_id(request_id=request.id, user_id="user-1")
    assert persisted is not None
    assert persisted.status == LocalRuntimeWorkStatus.FAILED
    assert "claim timeout" in (persisted.failure_reason or "")


@pytest.mark.asyncio
async def test_sweep_does_not_fail_recently_created_pending_request(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-2",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-2",
    )
    await async_session.commit()

    service = _sweep_service(async_session, claim_timeout=timedelta(seconds=60))
    claim_timeouts, _ = await service.sweep()

    assert claim_timeouts == 0
    persisted = await repo.get_by_id(request_id=request.id, user_id="user-2")
    assert persisted is not None
    assert persisted.status == LocalRuntimeWorkStatus.PENDING


@pytest.mark.asyncio
async def test_sweep_fails_claimed_request_with_stale_heartbeat(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-3",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-3",
    )
    await async_session.commit()
    claimed = await repo.claim_next_pending(user_id="user-3")
    await async_session.commit()
    assert claimed is not None
    await _backdate(
        async_session,
        request_id=request.id,
        column="heartbeat_at",
        when=datetime.now(UTC) - timedelta(minutes=5),
    )

    service = _sweep_service(async_session, heartbeat_timeout=timedelta(seconds=30))
    claim_timeouts, heartbeat_timeouts = await service.sweep()

    assert claim_timeouts == 0
    assert heartbeat_timeouts == 1
    persisted = await repo.get_by_id(request_id=request.id, user_id="user-3")
    assert persisted is not None
    assert persisted.status == LocalRuntimeWorkStatus.FAILED
    assert "heartbeating" in (persisted.failure_reason or "")


@pytest.mark.asyncio
async def test_sweep_does_not_fail_claimed_request_with_fresh_heartbeat(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-4",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-4",
    )
    await async_session.commit()
    await repo.claim_next_pending(user_id="user-4")
    await async_session.commit()

    service = _sweep_service(async_session, heartbeat_timeout=timedelta(seconds=30))
    _, heartbeat_timeouts = await service.sweep()

    assert heartbeat_timeouts == 0
    persisted = await repo.get_by_id(request_id=request.id, user_id="user-4")
    assert persisted is not None
    assert persisted.status == LocalRuntimeWorkStatus.CLAIMED
