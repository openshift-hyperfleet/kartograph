"""ORM model for extraction agent sessions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, _utc_now


class ExtractionAgentSessionModel(Base):
    """Persistence model for long-running extraction sessions."""

    __tablename__ = "extraction_agent_sessions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    knowledge_graph_id: Mapped[str] = mapped_column(String(26), nullable=False)
    mode: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_management_ui_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_history: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    runtime_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=_utc_now,
        onupdate=_utc_now,
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "idx_extract_sessions_scope_active",
            "user_id",
            "knowledge_graph_id",
            "mode",
            "archived_at",
        ),
        Index(
            "idx_extract_sessions_ui_mode_active",
            "user_id",
            "knowledge_graph_id",
            "graph_management_ui_mode",
            "archived_at",
        ),
        Index(
            "idx_extract_sessions_scope_updated",
            "user_id",
            "knowledge_graph_id",
            "updated_at",
        ),
        CheckConstraint(
            "mode IN ('schema_bootstrap', 'extraction_operations')",
            name="ck_extract_sessions_mode",
        ),
    )

