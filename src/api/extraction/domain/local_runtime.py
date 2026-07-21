"""Domain types for local-runtime Sandbox execution work requests.

See `specs/extraction/local-sandbox-execution.spec.md` for the behavior these
types support: dispatching Sandbox lifecycle and chat-turn work to a local
agent when hosted OpenShell execution is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class LocalRuntimeWorkKind(StrEnum):
    """What a local agent is being asked to do."""

    SANDBOX_START = "sandbox_start"
    CHAT_TURN = "chat_turn"
    SANDBOX_STOP = "sandbox_stop"


class LocalRuntimeWorkStatus(StrEnum):
    """Lifecycle status of one local runtime work request."""

    PENDING = "pending"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class LocalRuntimeWorkRequest:
    """One unit of Sandbox work dispatched to a user's local agent."""

    id: str
    tenant_id: str
    user_id: str
    knowledge_graph_id: str
    kind: LocalRuntimeWorkKind
    status: LocalRuntimeWorkStatus
    session_id: str | None = None
    job_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    failure_reason: str | None = None
    claimed_by_user_id: str | None = None
    claimed_at: datetime | None = None
    heartbeat_at: datetime | None = None
    completed_at: datetime | None = None
    credential_expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class LocalRuntimeAgentPresence:
    """Liveness bookkeeping for a user's local agent (not a credential)."""

    user_id: str
    tenant_id: str
    last_seen_at: datetime
