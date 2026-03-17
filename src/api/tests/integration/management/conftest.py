"""Integration test fixtures for Management bounded context.

These fixtures require a running PostgreSQL instance.
Database settings follow the same pattern as IAM integration tests.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from infrastructure.database.engines import create_write_engine
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.settings import DatabaseSettings
from management.infrastructure.repositories.data_source_repository import (
    DataSourceRepository,
)
from management.infrastructure.repositories.data_source_sync_run_repository import (
    DataSourceSyncRunRepository,
)
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def management_db_settings() -> DatabaseSettings:
    """Database settings for Management integration tests."""
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


@pytest_asyncio.fixture
async def async_session(
    management_db_settings: DatabaseSettings,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for integration tests."""
    engine = create_write_engine(management_db_settings)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    management_db_settings: DatabaseSettings,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Provide a session factory for tests that need to create multiple sessions.

    This is needed for components that create their own sessions.
    """
    engine = create_write_engine(management_db_settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    yield factory

    await engine.dispose()


@pytest_asyncio.fixture
async def clean_management_data(
    async_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    """Clean Management tables before and after tests.

    Deletion order respects FK constraints:
    outbox (management events) -> data_source_sync_runs ->
    data_sources -> knowledge_graphs

    Guards against tables not existing yet (TDD-first: tests may be
    collected before migration runs).
    """

    async def cleanup() -> None:
        """Perform cleanup with proper FK constraint ordering."""
        try:
            # Clean encrypted credentials first
            await async_session.execute(text("DELETE FROM encrypted_credentials"))
            # Clean management-related outbox entries
            await async_session.execute(
                text(
                    "DELETE FROM outbox WHERE aggregate_type "
                    "IN ('knowledge_graph', 'data_source')"
                )
            )
            await async_session.execute(text("DELETE FROM data_source_sync_runs"))
            await async_session.execute(text("DELETE FROM data_sources"))
            await async_session.execute(text("DELETE FROM knowledge_graphs"))
            await async_session.commit()
        except ProgrammingError:
            # Tables may not exist yet if migration hasn't run
            await async_session.rollback()

    # Clean before test
    await cleanup()

    yield

    # Clean after test
    await cleanup()


@pytest.fixture
def knowledge_graph_repository(
    async_session: AsyncSession,
) -> KnowledgeGraphRepository:
    """Provide a KnowledgeGraphRepository for integration tests."""
    outbox = OutboxRepository(session=async_session)
    return KnowledgeGraphRepository(session=async_session, outbox=outbox)


@pytest.fixture
def data_source_repository(
    async_session: AsyncSession,
) -> DataSourceRepository:
    """Provide a DataSourceRepository for integration tests."""
    outbox = OutboxRepository(session=async_session)
    return DataSourceRepository(session=async_session, outbox=outbox)


@pytest.fixture
def data_source_sync_run_repository(
    async_session: AsyncSession,
) -> DataSourceSyncRunRepository:
    """Provide a DataSourceSyncRunRepository for integration tests."""
    return DataSourceSyncRunRepository(session=async_session)


@pytest_asyncio.fixture
async def test_tenant(
    async_session: AsyncSession,
    clean_management_data: None,
) -> AsyncGenerator[str, None]:
    """Create a tenant in the tenants table for FK satisfaction.

    Uses raw SQL to insert directly, avoiding dependency on IAM domain objects.
    Cleans up the test tenant on teardown.
    Returns the tenant_id string.
    """
    tenant_id = str(ULID())
    await async_session.execute(
        text(
            "INSERT INTO tenants (id, name, created_at, updated_at) "
            "VALUES (:id, :name, NOW(), NOW())"
        ),
        {"id": tenant_id, "name": f"test-tenant-{tenant_id}"},
    )
    await async_session.commit()

    yield tenant_id

    # Teardown: remove test tenant (workspaces cleaned first by test_workspace)
    try:
        await async_session.execute(
            text("DELETE FROM workspaces WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        await async_session.execute(
            text("DELETE FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        )
        await async_session.commit()
    except ProgrammingError:
        await async_session.rollback()


@pytest_asyncio.fixture
async def test_workspace(
    async_session: AsyncSession,
    test_tenant: str,
) -> AsyncGenerator[str, None]:
    """Create a workspace in the workspaces table for FK satisfaction.

    Depends on test_tenant to ensure a valid tenant_id FK reference.
    Uses raw SQL to insert directly, avoiding dependency on IAM domain objects.
    Returns the workspace_id string.
    """
    workspace_id = str(ULID())
    await async_session.execute(
        text(
            "INSERT INTO workspaces (id, tenant_id, name, is_root, created_at, updated_at) "
            "VALUES (:id, :tenant_id, :name, :is_root, NOW(), NOW())"
        ),
        {
            "id": workspace_id,
            "tenant_id": test_tenant,
            "name": f"test-workspace-{workspace_id}",
            "is_root": True,
        },
    )
    await async_session.commit()

    yield workspace_id
