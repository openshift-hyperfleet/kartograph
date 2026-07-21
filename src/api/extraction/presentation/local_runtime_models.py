"""Pydantic models for local agent poll/claim/heartbeat/complete HTTP calls."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from extraction.domain.local_runtime import LocalRuntimeWorkRequest


class LocalRuntimeWorkRequestResponse(BaseModel):
    """A unit of Sandbox work claimed by a polling local agent."""

    id: str
    knowledge_graph_id: str
    session_id: str | None = None
    job_id: str | None = None
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def from_domain(
        cls, request: LocalRuntimeWorkRequest
    ) -> "LocalRuntimeWorkRequestResponse":
        return cls(
            id=request.id,
            knowledge_graph_id=request.knowledge_graph_id,
            session_id=request.session_id,
            job_id=request.job_id,
            kind=request.kind.value,
            payload=request.payload,
            created_at=request.created_at,
        )


class LocalRuntimeCompleteRequest(BaseModel):
    """Body for reporting a work request as completed."""

    result: dict[str, Any] = Field(default_factory=dict)


class LocalRuntimeFailRequest(BaseModel):
    """Body for reporting a work request as failed."""

    failure_reason: str = Field(min_length=1, max_length=2000)
