"""SQLAlchemy declarative base and shared model utilities.

This module provides the declarative base class for all SQLAlchemy ORM models
and common mixins for timestamps and other shared functionality.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All models in the application should inherit from this base class.
    It provides the declarative base functionality and type hints for SQLAlchemy 2.0.
    """

    # Type annotation for SQLAlchemy
    type_annotation_map: dict[type, Any] = {}


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamp columns.

    Automatically sets created_at on insert and updates updated_at on modification.
    Uses timezone-aware UTC timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
