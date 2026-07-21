"""Background sweep for stuck local-runtime work requests.

See specs/extraction/local-sandbox-execution.spec.md, "Claim timeout" and
"Heartbeat loss fails the claim". No local agent polling is required to
observe these failures -- pending requests no agent ever claimed, and
claimed requests whose agent stopped heartbeating, are failed here so the
originating session or job can surface a timeout instead of waiting
forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from extraction.ports.repositories import ILocalRuntimeRepository

_CLAIM_TIMEOUT_REASON = (
    "No local agent claimed this request within the claim timeout. Ensure "
    "your local agent is running and connected."
)
_HEARTBEAT_TIMEOUT_REASON = (
    "The claiming local agent stopped heartbeating. It may have crashed or "
    "lost connectivity."
)


class LocalRuntimeSweepService:
    """Fails timed-out pending and stale claimed local runtime work requests."""

    def __init__(
        self,
        *,
        repository: ILocalRuntimeRepository,
        claim_timeout: timedelta,
        heartbeat_timeout: timedelta,
    ) -> None:
        self._repository = repository
        self._claim_timeout = claim_timeout
        self._heartbeat_timeout = heartbeat_timeout

    async def sweep(self, *, now: datetime | None = None) -> tuple[int, int]:
        """Fail timed-out requests; return (claim_timeouts, heartbeat_timeouts)."""
        resolved_now = now or datetime.now(UTC)
        claim_timeouts = await self._repository.fail_timed_out_pending(
            older_than=resolved_now - self._claim_timeout,
            failure_reason=_CLAIM_TIMEOUT_REASON,
        )
        heartbeat_timeouts = await self._repository.fail_stale_claims(
            older_than=resolved_now - self._heartbeat_timeout,
            failure_reason=_HEARTBEAT_TIMEOUT_REASON,
        )
        return claim_timeouts, heartbeat_timeouts
