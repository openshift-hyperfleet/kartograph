"""SQLAlchemy ORM models for local-runtime Sandbox execution."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin, _utc_now


class LocalRuntimeAgentPresenceModel(Base):
    """Liveness bookkeeping for a user's local agent (not a credential)."""

    __tablename__ = "local_runtime_agent_presence"

    user_id: Mapped[str] = mapped_column(sa.String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(sa.String(26), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        insert_default=_utc_now,
        onupdate=_utc_now,
        nullable=False,
    )

    __table_args__ = (
        sa.Index("idx_local_runtime_presence_tenant", "tenant_id"),
    )


class LocalRuntimeWorkRequestModel(Base, TimestampMixin):
    """One unit of Sandbox work dispatched to a user's local agent."""

    __tablename__ = "local_runtime_work_requests"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(sa.String(26), nullable=False)
    user_id: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    knowledge_graph_id: Mapped[str] = mapped_column(sa.String(26), nullable=False)
    session_id: Mapped[str | None] = mapped_column(sa.String(26), nullable=True)
    job_id: Mapped[str | None] = mapped_column(sa.String(26), nullable=True)
    kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    claimed_by_user_id: Mapped[str | None] = mapped_column(
        sa.String(255), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    credential_expires_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        sa.CheckConstraint(
            "kind IN ('sandbox_start', 'chat_turn', 'sandbox_stop')",
            name="ck_local_runtime_work_requests_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'claimed', 'completed', 'failed')",
            name="ck_local_runtime_work_requests_status",
        ),
        sa.Index(
            "idx_local_runtime_work_requests_user_status", "user_id", "status"
        ),
        sa.Index(
            "idx_local_runtime_work_requests_session_status",
            "session_id",
            "status",
        ),
        sa.Index(
            "idx_local_runtime_work_requests_job_status", "job_id", "status"
        ),
    )
