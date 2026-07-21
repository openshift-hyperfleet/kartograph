"""PostgreSQL repository for local-runtime Sandbox execution work requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from extraction.domain.local_runtime import (
    LocalRuntimeAgentPresence,
    LocalRuntimeWorkKind,
    LocalRuntimeWorkRequest,
    LocalRuntimeWorkStatus,
)
from extraction.infrastructure.models.local_runtime import (
    LocalRuntimeAgentPresenceModel,
    LocalRuntimeWorkRequestModel,
)


def _request_model_to_record(
    model: LocalRuntimeWorkRequestModel,
) -> LocalRuntimeWorkRequest:
    return LocalRuntimeWorkRequest(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        knowledge_graph_id=model.knowledge_graph_id,
        session_id=model.session_id,
        job_id=model.job_id,
        kind=LocalRuntimeWorkKind(model.kind),
        status=LocalRuntimeWorkStatus(model.status),
        payload=dict(model.payload or {}),
        result=dict(model.result) if model.result is not None else None,
        failure_reason=model.failure_reason,
        claimed_by_user_id=model.claimed_by_user_id,
        claimed_at=model.claimed_at,
        heartbeat_at=model.heartbeat_at,
        completed_at=model.completed_at,
        credential_expires_at=model.credential_expires_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class LocalRuntimeRepository:
    """Persistence for local agent presence and dispatched work requests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_presence(self, *, user_id: str, tenant_id: str) -> None:
        """Upsert the caller's last-seen timestamp on poll."""
        now = datetime.now(UTC)
        stmt = (
            pg_insert(LocalRuntimeAgentPresenceModel)
            .values(user_id=user_id, tenant_id=tenant_id, last_seen_at=now)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"last_seen_at": now, "tenant_id": tenant_id},
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_presence(self, *, user_id: str) -> LocalRuntimeAgentPresence | None:
        stmt = select(LocalRuntimeAgentPresenceModel).where(
            LocalRuntimeAgentPresenceModel.user_id == user_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return LocalRuntimeAgentPresence(
            user_id=model.user_id,
            tenant_id=model.tenant_id,
            last_seen_at=model.last_seen_at,
        )

    async def enqueue_work_request(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        kind: LocalRuntimeWorkKind,
        session_id: str | None = None,
        job_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> LocalRuntimeWorkRequest:
        model = LocalRuntimeWorkRequestModel(
            id=str(ULID()),
            tenant_id=tenant_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            session_id=session_id,
            job_id=job_id,
            kind=kind.value,
            status=LocalRuntimeWorkStatus.PENDING.value,
            payload=payload or {},
        )
        self._session.add(model)
        await self._session.flush()
        return _request_model_to_record(model)

    async def claim_next_pending(
        self, *, user_id: str
    ) -> LocalRuntimeWorkRequest | None:
        """Claim the oldest pending request for the polling user's own work.

        Uses ``SKIP LOCKED`` so concurrent polls from the same user's multiple
        agent processes never claim the same row twice.
        """
        stmt = (
            select(LocalRuntimeWorkRequestModel)
            .where(
                LocalRuntimeWorkRequestModel.user_id == user_id,
                LocalRuntimeWorkRequestModel.status
                == LocalRuntimeWorkStatus.PENDING.value,
            )
            .order_by(LocalRuntimeWorkRequestModel.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        now = datetime.now(UTC)
        model.status = LocalRuntimeWorkStatus.CLAIMED.value
        model.claimed_by_user_id = user_id
        model.claimed_at = now
        model.heartbeat_at = now
        await self._session.flush()
        return _request_model_to_record(model)

    async def record_heartbeat(self, *, request_id: str, user_id: str) -> bool:
        result = await self._session.execute(
            update(LocalRuntimeWorkRequestModel)
            .where(
                LocalRuntimeWorkRequestModel.id == request_id,
                LocalRuntimeWorkRequestModel.user_id == user_id,
                LocalRuntimeWorkRequestModel.status
                == LocalRuntimeWorkStatus.CLAIMED.value,
            )
            .values(heartbeat_at=datetime.now(UTC))
        )
        return int(cast(CursorResult[Any], result).rowcount or 0) > 0

    async def mark_completed(
        self, *, request_id: str, user_id: str, result: dict[str, Any] | None = None
    ) -> bool:
        db_result = await self._session.execute(
            update(LocalRuntimeWorkRequestModel)
            .where(
                LocalRuntimeWorkRequestModel.id == request_id,
                LocalRuntimeWorkRequestModel.user_id == user_id,
                LocalRuntimeWorkRequestModel.status
                == LocalRuntimeWorkStatus.CLAIMED.value,
            )
            .values(
                status=LocalRuntimeWorkStatus.COMPLETED.value,
                result=result or {},
                completed_at=datetime.now(UTC),
            )
        )
        return int(cast(CursorResult[Any], db_result).rowcount or 0) > 0

    async def mark_failed(
        self, *, request_id: str, user_id: str, failure_reason: str
    ) -> bool:
        """Fail one of the caller's own requests, from `pending` or `claimed`.

        Always scoped by `user_id` (never optional) and guarded to only
        transition non-terminal requests, so an already-`completed` or
        already-`failed` row can never be overwritten.
        """
        result = await self._session.execute(
            update(LocalRuntimeWorkRequestModel)
            .where(
                LocalRuntimeWorkRequestModel.id == request_id,
                LocalRuntimeWorkRequestModel.user_id == user_id,
                LocalRuntimeWorkRequestModel.status.in_(
                    (
                        LocalRuntimeWorkStatus.PENDING.value,
                        LocalRuntimeWorkStatus.CLAIMED.value,
                    )
                ),
            )
            .values(
                status=LocalRuntimeWorkStatus.FAILED.value,
                failure_reason=failure_reason,
                completed_at=datetime.now(UTC),
            )
        )
        return int(cast(CursorResult[Any], result).rowcount or 0) > 0

    async def get_by_id(
        self, *, request_id: str, user_id: str
    ) -> LocalRuntimeWorkRequest | None:
        """Fetch one of the caller's own requests.

        Always scoped by `user_id`: a work request's id is a ULID, not a
        capability token, so callers must never be able to read another
        user's request by guessing or being handed its id.
        """
        stmt = select(LocalRuntimeWorkRequestModel).where(
            LocalRuntimeWorkRequestModel.id == request_id,
            LocalRuntimeWorkRequestModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _request_model_to_record(model)

    async def fail_timed_out_pending(
        self, *, older_than: datetime, failure_reason: str
    ) -> int:
        """Fail pending requests no agent claimed within the claim timeout."""
        result = await self._session.execute(
            update(LocalRuntimeWorkRequestModel)
            .where(
                LocalRuntimeWorkRequestModel.status
                == LocalRuntimeWorkStatus.PENDING.value,
                LocalRuntimeWorkRequestModel.created_at < older_than,
            )
            .values(
                status=LocalRuntimeWorkStatus.FAILED.value,
                failure_reason=failure_reason,
                completed_at=datetime.now(UTC),
            )
        )
        return int(cast(CursorResult[Any], result).rowcount or 0)

    async def fail_stale_claims(
        self, *, older_than: datetime, failure_reason: str
    ) -> int:
        """Fail claimed requests whose agent stopped heartbeating."""
        result = await self._session.execute(
            update(LocalRuntimeWorkRequestModel)
            .where(
                LocalRuntimeWorkRequestModel.status
                == LocalRuntimeWorkStatus.CLAIMED.value,
                LocalRuntimeWorkRequestModel.heartbeat_at < older_than,
            )
            .values(
                status=LocalRuntimeWorkStatus.FAILED.value,
                failure_reason=failure_reason,
                completed_at=datetime.now(UTC),
            )
        )
        return int(cast(CursorResult[Any], result).rowcount or 0)
