"""SQLAlchemy ORM model for the sync_jobs table."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, _utc_now


class SyncJobModel(Base):
    """ORM model for sync_jobs table.

    Stores sync job execution records in PostgreSQL. Each sync job
    tracks a data source synchronization request and its lifecycle status.

    Does not use TimestampMixin — sync jobs have only created_at
    (status transitions are tracked via started_at / completed_at).
    """

    __tablename__ = "sync_jobs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    data_source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    knowledge_graph_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=_utc_now,
        nullable=False,
    )

    __table_args__ = (
        Index("idx_sync_jobs_data_source_id", "data_source_id"),
        Index("idx_sync_jobs_tenant_id", "tenant_id"),
        Index("idx_sync_jobs_status", "status"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_sync_jobs_status",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<SyncJobModel(id={self.id}, "
            f"data_source_id={self.data_source_id}, status={self.status})>"
        )
