"""Bridge for calling the async local-runtime repository from sync adapters.

`IStickySessionRuntimeManager` (and sibling ports) are synchronous Protocols
invoked via `asyncio.to_thread` from application services, so they cannot
`await` directly. Each call here opens a short-lived engine with `NullPool`
and disposes it before returning, following the same bridging pattern this
codebase already uses in `infrastructure/migrations/env.py` for running
Alembic (a sync entrypoint) against the async engine.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from extraction.infrastructure.repositories.local_runtime_repository import (
    LocalRuntimeRepository,
)
from infrastructure.database.engines import build_async_url
from infrastructure.settings import DatabaseSettings, get_database_settings

T = TypeVar("T")


async def run_with_local_runtime_repository(
    fn: Callable[[LocalRuntimeRepository, AsyncSession], Awaitable[T]],
    *,
    db_settings: DatabaseSettings | None = None,
) -> T:
    """Open a short-lived session, run `fn`, and dispose the engine.

    `fn` receives both the repository and its backing session, since the
    repository intentionally never commits on its own (callers own the
    unit of work) but this bridge's whole purpose is to own one -- most
    callers need at least one explicit commit so writes become visible to
    other sessions (for example, a local agent polling from its own
    connection).
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    resolved_settings = db_settings or get_database_settings()
    engine = create_async_engine(build_async_url(resolved_settings), poolclass=NullPool)
    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with sessionmaker() as session:
            repo = LocalRuntimeRepository(session)
            return await fn(repo, session)
    finally:
        await engine.dispose()
