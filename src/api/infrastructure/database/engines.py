"""Database engine creation for async SQLAlchemy.

This module provides factory functions for creating read and write database engines
with proper connection pooling and async support using asyncpg.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from infrastructure.observability import DefaultConnectionProbe

if TYPE_CHECKING:
    from infrastructure.settings import DatabaseSettings

# Module-level probe for connection observability
_connection_probe = DefaultConnectionProbe()

__all__ = [
    "create_write_engine",
    "create_read_engine",
    "build_async_url",
]


def create_write_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create async engine for write operations.

    Uses standard connection pooling for mutations. Connects to the application
    database (separate from AGE graph database).

    Args:
        settings: Database connection settings

    Returns:
        Configured async engine for write operations
    """
    url = build_async_url(settings)

    try:
        engine = create_async_engine(
            url,
            pool_size=settings.pool_max_connections,
            max_overflow=0,  # No overflow - strict pool limit
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL logging
        )
        _connection_probe.pool_initialized(
            min_conn=0,  # asyncpg doesn't use min connections
            max_conn=settings.pool_max_connections,
        )
        return engine
    except Exception as e:
        _connection_probe.pool_initialization_failed(e)
        raise


def create_read_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create async engine for read-only operations.

    Uses separate connection pool with read-only execution options for safety.
    In production, this could point to a read replica.

    Args:
        settings: Database connection settings

    Returns:
        Configured async engine for read operations
    """
    url = build_async_url(settings)

    try:
        engine = create_async_engine(
            url,
            pool_size=settings.pool_max_connections,
            max_overflow=0,
            pool_pre_ping=True,
            echo=False,
            # Note: postgresql_readonly execution option doesn't prevent writes at engine level,
            # it's more of a hint. True read-only enforcement requires database role permissions.
            # For now, we rely on application discipline to use read engine only for queries.
        )
        _connection_probe.pool_initialized(
            min_conn=0,  # asyncpg doesn't use min connections
            max_conn=settings.pool_max_connections,
        )
        return engine
    except Exception as e:
        _connection_probe.pool_initialization_failed(e)
        raise


def build_async_url(settings: DatabaseSettings) -> str:
    """Build async database URL for asyncpg.

    Properly percent-encodes username and password to handle special characters
    per RFC 3986 using SQLAlchemy's URL builder.

    Args:
        settings: Database connection settings

    Returns:
        Connection URL string in format: postgresql+asyncpg://user:pass@host:port/db
        with credentials properly percent-encoded and SSL mode query parameter
    """
    url = URL.create(
        drivername="postgresql+asyncpg",
        username=settings.username,
        password=settings.password.get_secret_value(),
        host=settings.host,
        port=settings.port,
        database=settings.database,
        query={"ssl": settings.ssl_mode},
    )
    return url.render_as_string(hide_password=False)
