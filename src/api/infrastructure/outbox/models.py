"""SQLAlchemy ORM models for the outbox pattern.

This module provides the database model for the outbox table used in
the transactional outbox pattern.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base
from shared_kernel.outbox.value_objects import OutboxEntry


class OutboxModel(Base):
    """ORM model for the outbox table.

    Stores domain events that need to be processed asynchronously and
    applied to SpiceDB for authorization consistency.

    The table uses partial indexes for efficient polling:
    - idx_outbox_unprocessed: For fetching pending entries
    - idx_outbox_failed: For monitoring failed entries (DLQ)
    """

    __tablename__ = "outbox"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    aggregate_type: Mapped[str] = mapped_column(String(255), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(26), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    # Retry/DLQ columns
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def is_failed(self) -> bool:
        """Check if this entry has been moved to the DLQ."""
        return self.failed_at is not None

    def to_value_object(self) -> OutboxEntry:
        """Convert this ORM model to an OutboxEntry value object.

        Returns:
            An immutable OutboxEntry with all fields copied from this model.
        """
        return OutboxEntry(
            id=self.id,
            aggregate_type=self.aggregate_type,
            aggregate_id=self.aggregate_id,
            event_type=self.event_type,
            payload=self.payload,
            occurred_at=self.occurred_at,
            processed_at=self.processed_at,
            created_at=self.created_at,
            retry_count=self.retry_count,
            last_error=self.last_error,
            failed_at=self.failed_at,
        )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<OutboxModel("
            f"id={self.id}, "
            f"aggregate_type={self.aggregate_type}, "
            f"event_type={self.event_type}, "
            f"processed_at={self.processed_at}, "
            f"retry_count={self.retry_count}"
            f")>"
        )
