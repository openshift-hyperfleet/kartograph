"""SQLAlchemy ORM model for the data_source_sync_runs table.

Stores sync run execution records in PostgreSQL. Each sync run
tracks the status and timing of a data source synchronization.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, _utc_now


class DataSourceSyncRunModel(Base):
    """ORM model for data_source_sync_runs table.

    Stores sync run execution records in PostgreSQL. Each sync run
    tracks the status and timing of a data source synchronization.

    Does not use TimestampMixin because sync runs are immutable records
    with only created_at (no updated_at).

    Foreign Key Constraints:
    - data_source_id references data_sources.id with CASCADE delete
      Sync runs are automatically deleted when a data source is deleted

    Lifecycle statuses:
    - pending: Initial state when sync run is created
    - ingesting: Data extraction pipeline is running
    - ai_extracting: AI entity extraction is in progress
    - applying: Graph mutations are being applied
    - completed: Sync finished successfully (terminal)
    - failed: Sync failed at any stage (terminal)
    """

    __tablename__ = "data_source_sync_runs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    data_source_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
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
        Index("idx_sync_runs_data_source_id", "data_source_id"),
        Index("idx_sync_runs_data_source_status", "data_source_id", "status"),
        CheckConstraint(
            "status IN ('pending', 'ingesting', 'ai_extracting', 'applying', "
            "'completed', 'failed')",
            name="ck_sync_runs_status",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<DataSourceSyncRunModel(id={self.id}, "
            f"data_source_id={self.data_source_id}, status={self.status})>"
        )
