"""Pydantic models for extraction session APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import ExtractionSessionMode


class ExtractionSessionResponse(BaseModel):
    """API model for extraction session state."""

    id: str
    user_id: str
    knowledge_graph_id: str
    mode: ExtractionSessionMode
    message_history: list[dict[str, Any]] = Field(default_factory=list)
    runtime_context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None

    @classmethod
    def from_domain(cls, session: ExtractionAgentSession) -> "ExtractionSessionResponse":
        return cls(
            id=session.id,
            user_id=session.user_id,
            knowledge_graph_id=session.knowledge_graph_id,
            mode=session.mode,
            message_history=session.message_history,
            runtime_context=session.runtime_context,
            created_at=session.created_at,
            updated_at=session.updated_at,
            archived_at=session.archived_at,
        )


class ExtractionSessionListResponse(BaseModel):
    """List response for scoped extraction sessions."""

    sessions: list[ExtractionSessionResponse]
    count: int

