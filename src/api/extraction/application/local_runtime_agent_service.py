"""Application service backing local agent poll/claim/heartbeat/complete HTTP calls.

See specs/extraction/local-sandbox-execution.spec.md, "Local Runtime Work
Request Lifecycle" and "Local Agent Presence Tracking". This service owns the
unit of work (explicit commit after each mutation, via the repository port's
`commit()`) since `LocalRuntimeRepository` intentionally never commits on its
own initiative.
"""

from __future__ import annotations

from typing import Any

from extraction.domain.local_runtime import (
    LocalRuntimeWorkRequest,
    LocalRuntimeWorkStatus,
)
from extraction.ports.repositories import ILocalRuntimeRepository


class LocalRuntimeWorkRequestNotClaimableError(RuntimeError):
    """Raised when a heartbeat/complete/fail targets a request the caller
    does not own, that does not exist, or is not in the state required for
    that transition (for example, completing an already-completed request).
    """


class LocalRuntimeAgentService:
    """Poll/claim/heartbeat/complete lifecycle for a user's own local agent."""

    def __init__(self, *, repository: ILocalRuntimeRepository) -> None:
        self._repository = repository

    async def poll_and_claim(
        self, *, user_id: str, tenant_id: str
    ) -> LocalRuntimeWorkRequest | None:
        """Record presence and claim at most one pending request for this user.

        Presence is recorded unconditionally so absence detection
        (specs "Local Agent Presence Tracking") reflects every poll, even
        polls that find no work.
        """
        await self._repository.record_presence(user_id=user_id, tenant_id=tenant_id)
        claimed = await self._repository.claim_next_pending(user_id=user_id)
        await self._repository.commit()
        return claimed

    async def reject_claim(self, *, request_id: str, user_id: str, reason: str) -> None:
        """Fail a just-claimed request whose authorization re-check failed.

        Called by the presentation layer after `poll_and_claim` returns a
        request tied to a knowledge graph the caller no longer has edit
        permission on (specs "Claim revalidates authorization").
        """
        await self._repository.mark_failed(
            request_id=request_id, user_id=user_id, failure_reason=reason
        )
        await self._repository.commit()

    async def heartbeat(self, *, request_id: str, user_id: str) -> None:
        ok = await self._repository.record_heartbeat(
            request_id=request_id, user_id=user_id
        )
        await self._repository.commit()
        if not ok:
            raise LocalRuntimeWorkRequestNotClaimableError(
                f"No claimed local runtime work request {request_id!r} owned by "
                f"the caller was found to heartbeat."
            )

    async def complete(
        self, *, request_id: str, user_id: str, result: dict[str, Any] | None = None
    ) -> None:
        ok = await self._repository.mark_completed(
            request_id=request_id, user_id=user_id, result=result
        )
        await self._repository.commit()
        if not ok:
            raise LocalRuntimeWorkRequestNotClaimableError(
                f"No claimed local runtime work request {request_id!r} owned by "
                f"the caller was found to complete."
            )

    async def get_claimed_request(
        self, *, request_id: str, user_id: str
    ) -> LocalRuntimeWorkRequest | None:
        """Look up a request only if it is owned by the caller and `claimed`.

        Used by the vertex-token endpoint (specs "Downscoped, Short-Lived
        Vertex Credential Injection") to scope token minting to a work
        request the caller has actually claimed, rather than trusting
        client-supplied tenant/knowledge-graph identifiers directly.
        """
        request = await self._repository.get_by_id(
            request_id=request_id, user_id=user_id
        )
        if request is None or request.status != LocalRuntimeWorkStatus.CLAIMED:
            return None
        return request

    async def fail(self, *, request_id: str, user_id: str, failure_reason: str) -> None:
        ok = await self._repository.mark_failed(
            request_id=request_id, user_id=user_id, failure_reason=failure_reason
        )
        await self._repository.commit()
        if not ok:
            raise LocalRuntimeWorkRequestNotClaimableError(
                f"No pending/claimed local runtime work request {request_id!r} "
                f"owned by the caller was found to fail."
            )
