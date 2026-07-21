"""Integration tests for local-runtime persistence (schema + repository).

Covers specs/extraction/local-sandbox-execution.spec.md requirements:
"Local Agent Presence Tracking" and "Local Runtime Work Request Lifecycle".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from extraction.domain.local_runtime import LocalRuntimeWorkKind, LocalRuntimeWorkStatus
from extraction.infrastructure.models.local_runtime import (
    LocalRuntimeWorkRequestModel,
)
from extraction.infrastructure.repositories.local_runtime_repository import (
    LocalRuntimeRepository,
)

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def clean_local_runtime_data(async_session):
    """Remove any leftover local-runtime rows before and after each test."""
    from sqlalchemy import text

    async def _wipe() -> None:
        await async_session.execute(
            text("DELETE FROM local_runtime_work_requests")
        )
        await async_session.execute(
            text("DELETE FROM local_runtime_agent_presence")
        )
        await async_session.commit()

    await _wipe()
    yield
    await _wipe()


@pytest.fixture
def repo(async_session) -> LocalRuntimeRepository:
    return LocalRuntimeRepository(async_session)


@pytest.mark.asyncio
async def test_presence_recorded_on_poll(
    async_session, clean_local_runtime_data, repo: LocalRuntimeRepository
) -> None:
    """Scenario: Presence recorded on poll."""
    await repo.record_presence(user_id="user-1", tenant_id="tenant-1")
    await async_session.commit()

    presence = await repo.get_presence(user_id="user-1")
    assert presence is not None
    assert presence.tenant_id == "tenant-1"
    first_seen = presence.last_seen_at

    # Re-poll with a different tenant_id: if the upsert were a no-op (e.g. an
    # `ON CONFLICT DO NOTHING` bug), this would still show "tenant-1" back.
    await repo.record_presence(user_id="user-1", tenant_id="tenant-2")
    await async_session.commit()
    presence_again = await repo.get_presence(user_id="user-1")
    assert presence_again is not None
    assert presence_again.tenant_id == "tenant-2"
    assert presence_again.last_seen_at >= first_seen


@pytest.mark.asyncio
async def test_no_local_agent_has_ever_polled(
    async_session, clean_local_runtime_data, repo: LocalRuntimeRepository
) -> None:
    """Scenario: No local agent has ever polled (no presence row exists)."""
    assert await repo.get_presence(user_id="no-such-user") is None


@pytest.mark.asyncio
async def test_claim_by_polling_agent(
    async_session, clean_local_runtime_data, repo: LocalRuntimeRepository
) -> None:
    """Scenario: Claim by polling agent."""
    created = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-1",
    )
    await async_session.commit()
    assert created.status == LocalRuntimeWorkStatus.PENDING

    claimed = await repo.claim_next_pending(user_id="user-1")
    await async_session.commit()
    assert claimed is not None
    assert claimed.id == created.id
    assert claimed.status == LocalRuntimeWorkStatus.CLAIMED
    assert claimed.claimed_by_user_id == "user-1"
    assert claimed.claimed_at is not None
    assert claimed.heartbeat_at is not None

    # Not offered to any other polling connection.
    assert await repo.claim_next_pending(user_id="user-1") is None


@pytest.mark.asyncio
async def test_claim_only_sees_own_users_work(
    async_session, clean_local_runtime_data, repo: LocalRuntimeRepository
) -> None:
    await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
    )
    await async_session.commit()

    assert await repo.claim_next_pending(user_id="user-2") is None


@pytest.mark.asyncio
async def test_heartbeat_completion_and_failure(
    async_session, clean_local_runtime_data, repo: LocalRuntimeRepository
) -> None:
    created = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.CHAT_TURN,
        payload={"message": "hello"},
    )
    await async_session.commit()
    await repo.claim_next_pending(user_id="user-1")
    await async_session.commit()

    assert await repo.record_heartbeat(request_id=created.id, user_id="user-1")
    await async_session.commit()

    assert await repo.mark_completed(
        request_id=created.id, user_id="user-1", result={"reply": "hi"}
    )
    await async_session.commit()

    final = await repo.get_by_id(request_id=created.id, user_id="user-1")
    assert final is not None
    assert final.status == LocalRuntimeWorkStatus.COMPLETED
    assert final.result == {"reply": "hi"}
    assert final.completed_at is not None

    # A completed request can no longer be heartbeated, re-completed, or failed.
    assert not await repo.record_heartbeat(request_id=created.id, user_id="user-1")
    assert not await repo.mark_completed(
        request_id=created.id, user_id="user-1", result={"reply": "should not apply"}
    )
    assert not await repo.mark_failed(
        request_id=created.id, user_id="user-1", failure_reason="should not apply"
    )
    await async_session.commit()
    unchanged = await repo.get_by_id(request_id=created.id, user_id="user-1")
    assert unchanged is not None
    assert unchanged.status == LocalRuntimeWorkStatus.COMPLETED
    assert unchanged.result == {"reply": "hi"}


@pytest.mark.asyncio
async def test_mark_failed_records_reason(
    async_session, clean_local_runtime_data, repo: LocalRuntimeRepository
) -> None:
    created = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
    )
    await async_session.commit()

    # A different user can never fail someone else's request.
    assert not await repo.mark_failed(
        request_id=created.id,
        user_id="user-2",
        failure_reason="cross-user attempt",
    )
    assert await repo.get_by_id(request_id=created.id, user_id="user-2") is None

    assert await repo.mark_failed(
        request_id=created.id,
        user_id="user-1",
        failure_reason="Landlock enforcement unavailable",
    )
    await async_session.commit()

    final = await repo.get_by_id(request_id=created.id, user_id="user-1")
    assert final is not None
    assert final.status == LocalRuntimeWorkStatus.FAILED
    assert final.failure_reason == "Landlock enforcement unavailable"


@pytest.mark.asyncio
async def test_claim_timeout_fails_stale_pending(
    async_session, clean_local_runtime_data, repo: LocalRuntimeRepository
) -> None:
    """Scenario: Claim timeout."""
    created = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
    )
    await async_session.commit()

    cutoff = datetime.now(UTC) + timedelta(seconds=1)
    failed_count = await repo.fail_timed_out_pending(
        older_than=cutoff, failure_reason="No local agent claimed this request in time"
    )
    await async_session.commit()
    assert failed_count == 1

    final = await repo.get_by_id(request_id=created.id, user_id="user-1")
    assert final is not None
    assert final.status == LocalRuntimeWorkStatus.FAILED
    assert final.failure_reason == "No local agent claimed this request in time"


@pytest.mark.asyncio
async def test_heartbeat_loss_fails_the_claim(
    async_session, clean_local_runtime_data, repo: LocalRuntimeRepository
) -> None:
    """Scenario: Heartbeat loss fails the claim."""
    created = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
    )
    await async_session.commit()
    await repo.claim_next_pending(user_id="user-1")
    await async_session.commit()

    cutoff = datetime.now(UTC) + timedelta(seconds=1)
    failed_count = await repo.fail_stale_claims(
        older_than=cutoff, failure_reason="Local agent heartbeat lost"
    )
    await async_session.commit()
    assert failed_count == 1

    final = await repo.get_by_id(request_id=created.id, user_id="user-1")
    assert final is not None
    assert final.status == LocalRuntimeWorkStatus.FAILED
    assert final.failure_reason == "Local agent heartbeat lost"


@pytest.mark.asyncio
async def test_invalid_kind_rejected_by_check_constraint(
    async_session, clean_local_runtime_data
) -> None:
    async_session.add(
        LocalRuntimeWorkRequestModel(
            id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            kind="not_a_real_kind",
            status=LocalRuntimeWorkStatus.PENDING.value,
        )
    )
    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


@pytest.mark.asyncio
async def test_invalid_status_rejected_by_check_constraint(
    async_session, clean_local_runtime_data
) -> None:
    async_session.add(
        LocalRuntimeWorkRequestModel(
            id="01ARZ3NDEKTSV4RRFFQ69G5FAW",
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            kind=LocalRuntimeWorkKind.SANDBOX_START.value,
            status="unknown",
        )
    )
    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()
