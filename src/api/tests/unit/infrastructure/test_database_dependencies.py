"""Unit tests for database dependency injection.

Tests the FastAPI dependency providers for async database sessions.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.database.dependencies import (
    close_database_connections,
    get_read_engine,
    get_read_session,
    get_write_engine,
    get_write_session,
)


@pytest.mark.asyncio
async def test_get_write_engine():
    """Test that get_write_engine returns an AsyncEngine."""
    engine = get_write_engine()

    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+asyncpg"


@pytest.mark.asyncio
async def test_get_read_engine():
    """Test that get_read_engine returns an AsyncEngine."""
    engine = get_read_engine()

    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+asyncpg"


@pytest.mark.asyncio
async def test_engines_are_singletons():
    """Test that engines are cached and reused."""
    write_engine_1 = get_write_engine()
    write_engine_2 = get_write_engine()

    read_engine_1 = get_read_engine()
    read_engine_2 = get_read_engine()

    # Same engine instance should be returned
    assert write_engine_1 is write_engine_2
    assert read_engine_1 is read_engine_2

    # But write and read engines should be different
    assert write_engine_1 is not read_engine_1


@pytest.mark.asyncio
async def test_get_write_session():
    """Test that get_write_session yields an AsyncSession."""
    async for session in get_write_session():
        assert isinstance(session, AsyncSession)
        assert session.bind is not None


@pytest.mark.asyncio
async def test_get_read_session():
    """Test that get_read_session yields an AsyncSession."""
    async for session in get_read_session():
        assert isinstance(session, AsyncSession)
        assert session.bind is not None


@pytest.mark.asyncio
async def test_write_session_uses_write_engine():
    """Test that write session is bound to write engine."""
    write_engine = get_write_engine()

    async for session in get_write_session():
        # Session should be bound to write engine
        assert session.bind.sync_engine is write_engine.sync_engine


@pytest.mark.asyncio
async def test_read_session_uses_read_engine():
    """Test that read session is bound to read engine."""
    read_engine = get_read_engine()

    async for session in get_read_session():
        # Session should be bound to read engine
        assert session.bind.sync_engine is read_engine.sync_engine


@pytest.mark.asyncio
async def test_sessions_properly_yielded():
    """Test that sessions are properly yielded from async generators."""
    session_count = 0

    async for session in get_write_session():
        session_count += 1
        # Session should be active (not in a transaction, but connection is open)
        assert isinstance(session, AsyncSession)

    # Should have yielded exactly one session
    assert session_count == 1


@pytest.mark.asyncio
async def test_close_database_connections():
    """Test that close_database_connections disposes engines."""
    # Get engines to ensure they're initialized
    write_engine = get_write_engine()
    read_engine = get_read_engine()

    # Close connections
    await close_database_connections()

    # After closing, getting engines again should create new instances
    new_write_engine = get_write_engine()
    new_read_engine = get_read_engine()

    # Should be new engine instances
    assert new_write_engine is not write_engine
    assert new_read_engine is not read_engine

    # Cleanup
    await close_database_connections()
