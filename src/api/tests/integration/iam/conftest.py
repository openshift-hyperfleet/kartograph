"""Integration test fixtures for IAM bounded context.

These fixtures require running PostgreSQL and SpiceDB instances.
"""

from collections.abc import AsyncGenerator
import os

import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.user_repository import UserRepository
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings
from shared_kernel.authorization.dependencies import get_spicedb_client
from shared_kernel.authorization.protocols import AuthorizationProvider


@pytest.fixture(scope="session")
def iam_db_settings() -> DatabaseSettings:
    """Database settings for IAM integration tests."""
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
    iam_db_settings: DatabaseSettings,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for integration tests."""
    engine = create_write_engine(iam_db_settings)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def spicedb_client() -> AuthorizationProvider:
    """Provide a SpiceDB client for integration tests.

    Uses the application's dependency injection to get a configured client
    from settings. This ensures tests use the same configuration as the app.
    """
    return get_spicedb_client()


@pytest_asyncio.fixture
async def clean_iam_data(
    async_session: AsyncSession, spicedb_client: AuthorizationProvider
):
    """Clean IAM tables and SpiceDB relationships before and after tests.

    Note: Requires migrations to be run first. If tables don't exist,
    this fixture will skip cleanup gracefully.
    """
    # Clean before test
    try:
        await async_session.execute(text("TRUNCATE TABLE groups CASCADE"))
        await async_session.execute(text("TRUNCATE TABLE users CASCADE"))
        await async_session.commit()
    except Exception:
        # Tables might not exist if migrations haven't been run
        await async_session.rollback()

    # Note: SpiceDB cleanup would require iterating over all relationships
    # For now, rely on test isolation

    yield

    # Clean after test
    try:
        await async_session.execute(text("TRUNCATE TABLE groups CASCADE"))
        await async_session.execute(text("TRUNCATE TABLE users CASCADE"))
        await async_session.commit()
    except Exception:
        await async_session.rollback()


@pytest.fixture
def group_repository(
    async_session: AsyncSession, spicedb_client: AuthorizationProvider
) -> GroupRepository:
    """Provide a GroupRepository for integration tests."""
    return GroupRepository(
        session=async_session,
        authz=spicedb_client,
    )


@pytest.fixture
def user_repository(async_session: AsyncSession) -> UserRepository:
    """Provide a UserRepository for integration tests."""
    return UserRepository(session=async_session)
