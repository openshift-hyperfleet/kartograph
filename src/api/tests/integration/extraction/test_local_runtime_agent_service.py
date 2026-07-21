"""Integration tests for LocalRuntimeAgentService against the real database.

Covers specs/extraction/local-sandbox-execution.spec.md, "Local Runtime Work
Request Lifecycle" and "Local Agent Presence Tracking".
"""

from __future__ import annotations

import pytest

from extraction.application.local_runtime_agent_service import (
    LocalRuntimeAgentService,
    LocalRuntimeWorkRequestNotClaimableError,
)
from extraction.domain.local_runtime import LocalRuntimeWorkKind, LocalRuntimeWorkStatus
from extraction.infrastructure.repositories.local_runtime_repository import (
    LocalRuntimeRepository,
)

pytestmark = pytest.mark.integration


def _service(async_session) -> LocalRuntimeAgentService:
    return LocalRuntimeAgentService(repository=LocalRuntimeRepository(async_session))


@pytest.mark.asyncio
async def test_poll_and_claim_records_presence_even_with_no_pending_work(
    async_session, clean_local_runtime_data
) -> None:
    service = _service(async_session)

    claimed = await service.poll_and_claim(user_id="user-1", tenant_id="tenant-1")

    assert claimed is None
    repo = LocalRuntimeRepository(async_session)
    presence = await repo.get_presence(user_id="user-1")
    assert presence is not None
    assert presence.tenant_id == "tenant-1"


@pytest.mark.asyncio
async def test_poll_and_claim_returns_oldest_pending_request(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    first = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-2",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-a",
    )
    await async_session.commit()

    service = _service(async_session)
    claimed = await service.poll_and_claim(user_id="user-2", tenant_id="tenant-1")

    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == LocalRuntimeWorkStatus.CLAIMED


@pytest.mark.asyncio
async def test_reject_claim_fails_the_request(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-3",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-b",
    )
    await async_session.commit()

    service = _service(async_session)
    claimed = await service.poll_and_claim(user_id="user-3", tenant_id="tenant-1")
    assert claimed is not None

    await service.reject_claim(
        request_id=claimed.id, user_id="user-3", reason="permission revoked"
    )

    persisted = await repo.get_by_id(request_id=request.id, user_id="user-3")
    assert persisted is not None
    assert persisted.status == LocalRuntimeWorkStatus.FAILED
    assert persisted.failure_reason == "permission revoked"


@pytest.mark.asyncio
async def test_heartbeat_updates_claimed_request(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-4",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-c",
    )
    await async_session.commit()

    service = _service(async_session)
    await service.poll_and_claim(user_id="user-4", tenant_id="tenant-1")
    await service.heartbeat(request_id=request.id, user_id="user-4")

    persisted = await repo.get_by_id(request_id=request.id, user_id="user-4")
    assert persisted is not None
    assert persisted.heartbeat_at is not None


@pytest.mark.asyncio
async def test_heartbeat_raises_for_unclaimed_request(
    async_session, clean_local_runtime_data
) -> None:
    service = _service(async_session)

    with pytest.raises(LocalRuntimeWorkRequestNotClaimableError):
        await service.heartbeat(request_id="nonexistent", user_id="user-5")


@pytest.mark.asyncio
async def test_complete_marks_request_completed_with_result(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-6",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-d",
    )
    await async_session.commit()

    service = _service(async_session)
    await service.poll_and_claim(user_id="user-6", tenant_id="tenant-1")
    await service.complete(
        request_id=request.id,
        user_id="user-6",
        result={"container_id": "sandbox-xyz"},
    )

    persisted = await repo.get_by_id(request_id=request.id, user_id="user-6")
    assert persisted is not None
    assert persisted.status == LocalRuntimeWorkStatus.COMPLETED
    assert persisted.result == {"container_id": "sandbox-xyz"}


@pytest.mark.asyncio
async def test_complete_raises_when_request_not_claimed_by_caller(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-7",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-e",
    )
    await async_session.commit()

    service = _service(async_session)
    # Never claimed -- still pending -- so complete must not succeed.
    with pytest.raises(LocalRuntimeWorkRequestNotClaimableError):
        await service.complete(request_id=request.id, user_id="user-7", result={})


@pytest.mark.asyncio
async def test_fail_marks_request_failed_with_reason(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-8",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-f",
    )
    await async_session.commit()

    service = _service(async_session)
    await service.poll_and_claim(user_id="user-8", tenant_id="tenant-1")
    await service.fail(
        request_id=request.id,
        user_id="user-8",
        failure_reason="Landlock enforcement unavailable",
    )

    persisted = await repo.get_by_id(request_id=request.id, user_id="user-8")
    assert persisted is not None
    assert persisted.status == LocalRuntimeWorkStatus.FAILED
    assert persisted.failure_reason == "Landlock enforcement unavailable"


@pytest.mark.asyncio
async def test_get_claimed_request_returns_claimed_request_for_owner(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-10",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-h",
    )
    await async_session.commit()

    service = _service(async_session)
    await service.poll_and_claim(user_id="user-10", tenant_id="tenant-1")

    found = await service.get_claimed_request(request_id=request.id, user_id="user-10")

    assert found is not None
    assert found.id == request.id
    assert found.status == LocalRuntimeWorkStatus.CLAIMED


@pytest.mark.asyncio
async def test_get_claimed_request_returns_none_for_still_pending_request(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-11",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-i",
    )
    await async_session.commit()

    service = _service(async_session)
    found = await service.get_claimed_request(request_id=request.id, user_id="user-11")

    assert found is None


@pytest.mark.asyncio
async def test_get_claimed_request_returns_none_for_another_user(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-12",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-j",
    )
    await async_session.commit()

    service = _service(async_session)
    await service.poll_and_claim(user_id="user-12", tenant_id="tenant-1")

    found = await service.get_claimed_request(
        request_id=request.id, user_id="someone-else"
    )

    assert found is None


@pytest.mark.asyncio
async def test_fail_raises_for_another_users_request(
    async_session, clean_local_runtime_data
) -> None:
    repo = LocalRuntimeRepository(async_session)
    request = await repo.enqueue_work_request(
        tenant_id="tenant-1",
        user_id="user-9",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        session_id="sess-g",
    )
    await async_session.commit()

    service = _service(async_session)
    with pytest.raises(LocalRuntimeWorkRequestNotClaimableError):
        await service.fail(
            request_id=request.id, user_id="someone-else", failure_reason="nope"
        )
