"""Integration test fixtures for the Ingestion bounded context.

These fixtures require a running PostgreSQL instance.
The sync_jobs table is created via raw SQL so no Alembic migration is needed.

Design: uses a minimal FastAPI app with only the ingestion router,
bypassing the full main.py lifespan (which requires SpiceDB and Keycloak).
This keeps ingestion tests auth-free and dependency-free.

Async fixtures are function-scoped (new engine per test) following the
management integration test pattern to avoid asyncpg event loop issues.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database.dependencies import get_write_session
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings
from ingestion.presentation import router as ingestion_router

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Database settings (sync, session-scoped — safe)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ingestion_db_settings() -> DatabaseSettings:
    """Database settings for Ingestion integration tests."""
    return DatabaseSettings(
        host=os.getenv("KARTOGRAPH_DB_HOST", "localhost"),
        port=int(os.getenv("KARTOGRAPH_DB_PORT", "5432")),
        database=os.getenv("KARTOGRAPH_DB_DATABASE", "kartograph"),
        username=os.getenv("KARTOGRAPH_DB_USERNAME", "kartograph"),
        password=SecretStr(
            os.getenv("KARTOGRAPH_DB_PASSWORD", "kartograph_dev_password")
        ),
        graph_name="test_graph",
    )


# ---------------------------------------------------------------------------
# Async session (function-scoped: new engine per test, avoids asyncpg loop issues)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_session(
    ingestion_db_settings: DatabaseSettings,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for each test.

    Creates and disposes the engine within the test's event loop.
    """
    engine = create_write_engine(ingestion_db_settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Table lifecycle (idempotent — runs before each test)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def ensure_sync_jobs_table(async_session: AsyncSession) -> None:
    """Create the sync_jobs table if it does not exist.

    Uses raw SQL — no Alembic migration required. Idempotent.
    """
    await async_session.execute(
        text("""
        CREATE TABLE IF NOT EXISTS sync_jobs (
            id               VARCHAR(26)  PRIMARY KEY,
            data_source_id   VARCHAR(255) NOT NULL,
            tenant_id        VARCHAR(255) NOT NULL,
            knowledge_graph_id VARCHAR(255),
            status           VARCHAR(50)  NOT NULL
                CHECK (status IN ('pending', 'running', 'completed', 'failed')),
            started_at       TIMESTAMPTZ,
            completed_at     TIMESTAMPTZ,
            error            TEXT,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """)
    )
    await async_session.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sync_jobs(
    async_session: AsyncSession,
    ensure_sync_jobs_table: None,
) -> AsyncGenerator[None, None]:
    """Delete all sync_jobs before and after each test for isolation."""

    async def _clean() -> None:
        try:
            await async_session.execute(text("DELETE FROM sync_jobs"))
            await async_session.commit()
        except ProgrammingError:
            await async_session.rollback()

    await _clean()
    yield
    await _clean()


# ---------------------------------------------------------------------------
# Minimal test app (function-scoped to share the test event loop)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(
    ingestion_db_settings: DatabaseSettings,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for the minimal ingestion test app.

    Creates a fresh FastAPI app with only the ingestion router.
    Overrides get_write_session to use a test database engine.
    No SpiceDB, no Keycloak — auth-free by design.
    """
    engine = create_write_engine(ingestion_db_settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _test_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    test_app = FastAPI(title="Ingestion Test App")
    test_app.include_router(ingestion_router)
    test_app.dependency_overrides[get_write_session] = _test_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()
