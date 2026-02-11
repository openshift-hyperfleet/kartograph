"""Database dependency injection for FastAPI.

Provides async session factories for read and write operations with proper
transaction management and connection pooling.

Engine Lifecycle:
    Engines are initialized in the FastAPI lifespan handler and stored on app.state.
    This ensures engines are created within the running event loop, avoiding
    async context issues in testing and production.

    The lifespan handler calls:
        - init_database_engines(app) on startup
        - close_database_engines(app) on shutdown
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Request, FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from infrastructure.database.engines import create_read_engine, create_write_engine
from infrastructure.observability import DefaultConnectionProbe
from infrastructure.settings import get_database_settings

# Module-level probe for observability
_probe = DefaultConnectionProbe()


def init_database_engines(app: FastAPI) -> None:
    """Initialize database engines and store on app.state.

    Must be called from FastAPI lifespan startup handler to ensure engines
    are created within the running event loop.

    Args:
        app: FastAPI application instance
    """
    settings = get_database_settings()

    # Create engines
    write_engine = create_write_engine(settings)
    read_engine = create_read_engine(settings)

    # Create sessionmakers
    write_sessionmaker = async_sessionmaker(
        write_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    read_sessionmaker = async_sessionmaker(
        read_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    # Store on app.state for access by dependencies
    app.state.write_engine = write_engine
    app.state.read_engine = read_engine
    app.state.write_sessionmaker = write_sessionmaker
    app.state.read_sessionmaker = read_sessionmaker


async def close_database_engines(app) -> None:
    """Close database engines on app shutdown.

    Must be called from FastAPI lifespan shutdown handler.

    Args:
        app: FastAPI application instance
    """
    if hasattr(app.state, "write_engine") and app.state.write_engine is not None:
        await app.state.write_engine.dispose()
        _probe.pool_closed()

    if hasattr(app.state, "read_engine") and app.state.read_engine is not None:
        await app.state.read_engine.dispose()
        _probe.pool_closed()


def get_write_engine(request: Request) -> AsyncEngine:
    """Get the write database engine from app.state (FastAPI dependency).

    Args:
        request: FastAPI request (injected)

    Returns:
        Configured async engine for write operations
    """
    return request.app.state.write_engine


def get_read_engine(request: Request) -> AsyncEngine:
    """Get the read database engine from app.state (FastAPI dependency).

    Args:
        request: FastAPI request (injected)

    Returns:
        Configured async engine for read operations
    """
    return request.app.state.read_engine


async def get_write_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
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

    Args:
        request: FastAPI request (injected)

    Yields:
        AsyncSession for database operations
    """
    sessionmaker = request.app.state.write_sessionmaker
    async with sessionmaker() as session:
        yield session


async def get_tenant_context_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a separate write session for tenant context resolution.

    This is intentionally a distinct dependency from get_write_session so that
    tenant context resolution (which may auto-add users to the default tenant)
    operates in its own transaction, independent of the main request session.

    Without this separation, the auto-add member write in resolve_tenant_context
    would start a transaction on the shared session, causing "A transaction is
    already begun" errors when the main request handler later calls
    session.begin().

    Args:
        request: FastAPI request (injected)

    Yields:
        AsyncSession for tenant context database operations
    """
    sessionmaker = request.app.state.write_sessionmaker
    async with sessionmaker() as session:
        yield session


async def get_read_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
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

    Args:
        request: FastAPI request (injected)

    Yields:
        AsyncSession for read-only database operations
    """
    sessionmaker = request.app.state.read_sessionmaker
    async with sessionmaker() as session:
        yield session
