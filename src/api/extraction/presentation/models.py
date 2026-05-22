"""Pydantic models for extraction session APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from extraction.application.agent_session_service import ExtractionSessionHistoryRecord
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import (
    BootstrapIntakePath,
    ExtractionSessionMode,
    ExtractionSessionRunMetric,
)


class SessionRunMetricResponse(BaseModel):
    """Run-level metrics linked to an extraction session."""

    sync_run_id: str
    mutation_log_id: str | None = None
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    token_usage_total: int | None = None
    cost_total_usd: float | None = None
    operation_counts: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, metric: ExtractionSessionRunMetric) -> "SessionRunMetricResponse":
        return cls(
            sync_run_id=metric.sync_run_id,
            mutation_log_id=metric.mutation_log_id,
            status=metric.status,
            started_at=metric.started_at,
            completed_at=metric.completed_at,
            token_usage_total=metric.token_usage_total,
            cost_total_usd=metric.cost_total_usd,
            operation_counts=dict(metric.operation_counts),
        )


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


class ExtractionSessionHistoryItemResponse(BaseModel):
    """Historical session summary with linked run metrics."""

    id: str
    user_id: str
    knowledge_graph_id: str
    mode: ExtractionSessionMode
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    is_active: bool
    message_count: int
    run_metrics: list[SessionRunMetricResponse] = Field(default_factory=list)

    @classmethod
    def from_history_record(
        cls,
        record: ExtractionSessionHistoryRecord,
    ) -> "ExtractionSessionHistoryItemResponse":
        session = record.session
        return cls(
            id=session.id,
            user_id=session.user_id,
            knowledge_graph_id=session.knowledge_graph_id,
            mode=session.mode,
            created_at=session.created_at,
            updated_at=session.updated_at,
            archived_at=session.archived_at,
            is_active=session.is_active,
            message_count=len(session.message_history),
            run_metrics=[
                SessionRunMetricResponse.from_domain(metric)
                for metric in record.run_metrics
            ],
        )


class ExtractionSessionHistoryResponse(BaseModel):
    """History response for scoped extraction sessions."""

    sessions: list[ExtractionSessionHistoryItemResponse]
    count: int


class BootstrapIntakePathSelectionRequest(BaseModel):
    """Request model for bootstrap intake path selection."""

    selected_path: BootstrapIntakePath
    capabilities_goals: str | None = Field(
        default=None,
        description="Optional user summary of capabilities and schema goals",
    )
