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
from shared_kernel.authorization.spicedb.client import SpiceDBClient


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
def spicedb_client() -> SpiceDBClient:
    """Provide a SpiceDB client for integration tests."""
    endpoint = os.getenv("SPICEDB_ENDPOINT", "localhost:50051")
    preshared_key = os.getenv("SPICEDB_PRESHARED_KEY", "test_key")

    return SpiceDBClient(
        endpoint=endpoint,
        preshared_key=preshared_key,
    )


@pytest_asyncio.fixture
async def clean_iam_data(async_session: AsyncSession, spicedb_client: SpiceDBClient):
    """Clean IAM tables and SpiceDB relationships before and after tests.

    Note: Requires migrations to be run first. If tables don't exist,
    this fixture will skip cleanup gracefully.
    """
    # Clean before test
    async with async_session.begin():
        try:
            await async_session.execute(text("TRUNCATE TABLE groups CASCADE"))
            await async_session.execute(text("TRUNCATE TABLE users CASCADE"))
        except Exception:
            # Tables might not exist if migrations haven't been run
            pass

    # Note: SpiceDB cleanup would require iterating over all relationships
    # For now, rely on test isolation

    yield

    # Clean after test
    async with async_session.begin():
        try:
            await async_session.execute(text("TRUNCATE TABLE groups CASCADE"))
            await async_session.execute(text("TRUNCATE TABLE users CASCADE"))
        except Exception:
            pass


@pytest.fixture
def group_repository(
    async_session: AsyncSession, spicedb_client: SpiceDBClient
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
