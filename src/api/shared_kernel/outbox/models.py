"""SQLAlchemy ORM models for the outbox pattern.

This module provides the database model for the outbox table used in
the transactional outbox pattern.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base


class OutboxModel(Base):
    """ORM model for the outbox table.

    Stores domain events that need to be processed asynchronously and
    applied to SpiceDB for authorization consistency.

    The table uses a partial index on unprocessed entries for efficient
    polling by the worker.
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

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<OutboxModel("
            f"id={self.id}, "
            f"aggregate_type={self.aggregate_type}, "
            f"event_type={self.event_type}, "
            f"processed_at={self.processed_at}"
            f")>"
        )
