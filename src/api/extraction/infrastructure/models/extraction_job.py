"""SQLAlchemy ORM models for extraction jobs and runs."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class ExtractionJobModel(Base, TimestampMixin):
    """Materialized extraction job assigned to one knowledge graph."""

    __tablename__ = "extraction_jobs"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True)
    knowledge_graph_id: Mapped[str] = mapped_column(sa.String(26), nullable=False)
    job_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    job_set_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    strategy: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    order_index: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    description: Mapped[str] = mapped_column(sa.Text(), nullable=False, default="")
    target_instances: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    target_files: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    worker_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    attempt: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(sa.Float(), nullable=False, default=0.0)
    entities_created: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    entities_modified: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    relationships_created: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)


class ExtractionRunModel(Base, TimestampMixin):
    """Orchestrator run state for one knowledge graph."""

    __tablename__ = "extraction_runs"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True)
    knowledge_graph_id: Mapped[str] = mapped_column(sa.String(26), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    worker_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=1)
    pause_requested: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    orchestrator_pid: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
