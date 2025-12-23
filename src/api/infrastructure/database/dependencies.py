"""Database dependency injection for FastAPI.

Provides async session factories for read and write operations with proper
transaction management and connection pooling.
"""

from __future__ import annotations

import threading
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from infrastructure.database.engines import create_read_engine, create_write_engine
from infrastructure.observability import DefaultConnectionProbe
from infrastructure.settings import get_database_settings

# Module-level probe for observability
_probe = DefaultConnectionProbe()

# Module-level engine instances (created on first use)
_write_engine: AsyncEngine | None = None
_read_engine: AsyncEngine | None = None

# Module-level sessionmaker instances (created with engines)
_write_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_read_sessionmaker: async_sessionmaker[AsyncSession] | None = None

# Thread lock for safe engine initialization
_engine_lock = threading.Lock()


def get_write_engine() -> AsyncEngine:
    """Get the write database engine (singleton).

    Creates engine on first call and caches for subsequent calls.
    Uses double-check locking for thread-safe initialization.
    Also creates and caches the sessionmaker for efficient session creation.

    Returns:
        Configured async engine for write operations
    """
    global _write_engine, _write_sessionmaker
    if _write_engine is None:
        with _engine_lock:
            # Double-check after acquiring lock
            if _write_engine is None:
                settings = get_database_settings()
                _write_engine = create_write_engine(settings)
                # Create sessionmaker once with the engine
                _write_sessionmaker = async_sessionmaker(
                    _write_engine,
                    expire_on_commit=False,
                    class_=AsyncSession,
                )
    return _write_engine


def get_read_engine() -> AsyncEngine:
    """Get the read database engine (singleton).

    Creates engine on first call and caches for subsequent calls.
    Uses double-check locking for thread-safe initialization.
    Also creates and caches the sessionmaker for efficient session creation.

    Returns:
        Configured async engine for read operations
    """
    global _read_engine, _read_sessionmaker
    if _read_engine is None:
        with _engine_lock:
            # Double-check after acquiring lock
            if _read_engine is None:
                settings = get_database_settings()
                _read_engine = create_read_engine(settings)
                # Create sessionmaker once with the engine
                _read_sessionmaker = async_sessionmaker(
                    _read_engine,
                    expire_on_commit=False,
                    class_=AsyncSession,
                )
    return _read_engine


async def get_write_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a write session for mutations (FastAPI dependency).

    The session is configured to NOT auto-commit. Callers must explicitly
    manage transactions using `async with session.begin()`.

    Usage:
        @router.post("/teams")
        async def create_team(
            session: AsyncSession = Depends(get_write_session)
        ):
            async with session.begin():
                # mutations here
                session.add(team)
                # transaction commits at end of `with` block

    Yields:
        AsyncSession for database operations
    """
    # Ensure engine and sessionmaker are initialized
    get_write_engine()
    assert _write_sessionmaker is not None

    async with _write_sessionmaker() as session:
        yield session


async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a read-only session for queries (FastAPI dependency).

    The session uses the read engine. While not enforced at the database level
    (requires database role permissions), application code should use this
    session only for read operations.

    Usage:
        @router.get("/teams/{id}")
        async def get_team(
            session: AsyncSession = Depends(get_read_session)
        ):
            result = await session.execute(select(Team).where(...))
            return result.scalar_one_or_none()

    Yields:
        AsyncSession for read-only database operations
    """
    # Ensure engine and sessionmaker are initialized
    get_read_engine()
    assert _read_sessionmaker is not None

    async with _read_sessionmaker() as session:
        yield session


async def close_database_connections() -> None:
    """Close all database engine connections.

    Should be called on application shutdown to properly cleanup connections.
    Also resets sessionmakers to allow reinitialization.
    """
    global _write_engine, _read_engine, _write_sessionmaker, _read_sessionmaker

    if _write_engine is not None:
        await _write_engine.dispose()
        _probe.pool_closed()
        _write_engine = None
        _write_sessionmaker = None

    if _read_engine is not None:
        await _read_engine.dispose()
        _probe.pool_closed()
        _read_engine = None
        _read_sessionmaker = None
