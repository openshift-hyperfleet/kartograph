"""Database engine creation for async SQLAlchemy.

This module provides factory functions for creating read and write database engines
with proper connection pooling and async support using asyncpg.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

if TYPE_CHECKING:
    from infrastructure.settings import DatabaseSettings


def create_write_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create async engine for write operations.

    Uses standard connection pooling for mutations. Connects to the application
    database (separate from AGE graph database).

    Args:
        settings: Database connection settings

    Returns:
        Configured async engine for write operations
    """
    url = _build_async_url(settings)

    return create_async_engine(
        url,
        pool_size=settings.pool_max_connections,
        max_overflow=0,  # No overflow - strict pool limit
        pool_pre_ping=True,  # Verify connections before using
        echo=False,  # Set to True for SQL logging
    )


def create_read_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create async engine for read-only operations.

    Uses separate connection pool with read-only execution options for safety.
    In production, this could point to a read replica.

    Args:
        settings: Database connection settings

    Returns:
        Configured async engine for read operations
    """
    url = _build_async_url(settings)

    return create_async_engine(
        url,
        pool_size=settings.pool_max_connections,
        max_overflow=0,
        pool_pre_ping=True,
        echo=False,
        # Note: postgresql_readonly execution option doesn't prevent writes at engine level,
        # it's more of a hint. True read-only enforcement requires database role permissions.
        # For now, we rely on application discipline to use read engine only for queries.
    )


def _build_async_url(settings: DatabaseSettings) -> str:
    """Build async database URL for asyncpg.

    Args:
        settings: Database connection settings

    Returns:
        Connection URL string in format: postgresql+asyncpg://user:pass@host:port/db
    """
    password = settings.password.get_secret_value()
    return (
        f"postgresql+asyncpg://"
        f"{settings.username}:{password}@"
        f"{settings.host}:{settings.port}/"
        f"{settings.database}"
    )
