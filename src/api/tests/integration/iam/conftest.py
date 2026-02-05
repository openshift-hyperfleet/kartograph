"""Integration test fixtures for IAM bounded context.

These fixtures require running PostgreSQL and SpiceDB instances.
SpiceDB settings are configured in the parent conftest.
"""

from collections.abc import AsyncGenerator, Callable, Coroutine
import os
from typing import Any

from jose import jwt
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iam.domain.aggregates import Tenant
from iam.domain.value_objects import TenantId
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.outbox import IAMEventTranslator
from iam.infrastructure.tenant_repository import TenantRepository
from iam.infrastructure.user_repository import UserRepository
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.engines import create_write_engine
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.outbox.worker import OutboxWorker
from infrastructure.settings import get_iam_settings
from infrastructure.settings import DatabaseSettings
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.outbox.observability import DefaultOutboxWorkerProbe


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


@pytest.fixture
def db_settings(iam_db_settings: DatabaseSettings) -> DatabaseSettings:
    """Provide database settings for integration tests.

    This is an alias for iam_db_settings with a simpler name for tests
    that need to construct database URLs.
    """
    return iam_db_settings


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


@pytest_asyncio.fixture
async def session_factory(
    iam_db_settings: DatabaseSettings,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Provide a session factory for tests that need to create multiple sessions.

    This is needed for the outbox worker which creates its own sessions.
    """
    engine = create_write_engine(iam_db_settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    yield factory

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

    With FK CASCADE constraints, deleting tenants automatically deletes
    groups and api_keys. Deletion order matters for referential integrity.

    Preserves the default tenant which is created at app startup and
    expected to exist for API integration tests.
    """
    # Get default tenant name from settings
    default_tenant_name = get_iam_settings().default_tenant_name

    # Clean before test
    try:
        # Use DELETE instead of TRUNCATE to avoid deadlocks in parallel tests
        # DELETE in correct order to respect FK constraints
        await async_session.execute(text("DELETE FROM outbox"))
        await async_session.execute(text("DELETE FROM api_keys"))  # FK to tenants
        await async_session.execute(text("DELETE FROM groups"))  # FK to tenants
        await async_session.execute(text("DELETE FROM users"))
        # Delete all tenants EXCEPT the default tenant
        await async_session.execute(
            text("DELETE FROM tenants WHERE name != :default_name"),
            {"default_name": default_tenant_name},
        )
        await async_session.commit()
    except Exception:
        # Tables might not exist if migrations haven't been run
        await async_session.rollback()

    # Note: SpiceDB cleanup would require iterating over all relationships
    # For now, rely on test isolation

    yield

    # Clean after test
    try:
        # DELETE in correct order to respect FK constraints
        await async_session.execute(text("DELETE FROM outbox"))
        await async_session.execute(text("DELETE FROM api_keys"))
        await async_session.execute(text("DELETE FROM groups"))
        await async_session.execute(text("DELETE FROM users"))
        # Delete all tenants EXCEPT the default tenant
        await async_session.execute(
            text("DELETE FROM tenants WHERE name != :default_name"),
            {"default_name": default_tenant_name},
        )
        await async_session.commit()
    except Exception:
        await async_session.rollback()


@pytest.fixture
def group_repository(
    async_session: AsyncSession, spicedb_client: AuthorizationProvider
) -> GroupRepository:
    """Provide a GroupRepository for integration tests."""
    outbox = OutboxRepository(session=async_session)
    return GroupRepository(
        session=async_session,
        authz=spicedb_client,
        outbox=outbox,
    )


@pytest.fixture
def user_repository(async_session: AsyncSession) -> UserRepository:
    """Provide a UserRepository for integration tests."""
    return UserRepository(session=async_session)


@pytest.fixture
def tenant_repository(async_session: AsyncSession) -> TenantRepository:
    """Provide a TenantRepository for integration tests."""
    outbox = OutboxRepository(session=async_session)
    return TenantRepository(
        session=async_session,
        outbox=outbox,
    )


@pytest_asyncio.fixture
async def test_tenant(
    tenant_repository: TenantRepository, async_session: AsyncSession, clean_iam_data
) -> TenantId:
    """Create a test tenant that persists for the duration of the test.

    This tenant can be used by tests that create groups, API keys, or other
    resources that require a valid tenant_id due to FK constraints.

    Depends on clean_iam_data to ensure a clean slate before creating the tenant.
    """
    tenant = Tenant.create(name="Test Tenant")

    async with async_session.begin():
        await tenant_repository.save(tenant)

    return tenant.id


@pytest_asyncio.fixture
async def process_outbox(
    session_factory: async_sessionmaker[AsyncSession],
    spicedb_client: AuthorizationProvider,
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Provide a function to process all pending outbox entries.

    Call this after saves to synchronously process outbox entries
    and write relationships to SpiceDB before assertions.
    """
    translator = IAMEventTranslator()
    probe = DefaultOutboxWorkerProbe()

    worker = OutboxWorker(
        session_factory=session_factory,
        authz=spicedb_client,
        translator=translator,
        probe=probe,
    )

    async def _process() -> None:
        """Process all pending outbox entries."""
        await worker._process_batch()

    return _process


def _extract_user_id_from_token(token: str, token_name: str) -> str:
    """Extract user_id (sub claim) from a JWT token.

    Helper function for test fixtures that need to extract the Keycloak
    user UUID from JWT tokens for setting up SpiceDB relationships.

    Args:
        token: JWT access token from Keycloak
        token_name: Name of the token (for error messages, e.g., "alice_token")

    Returns:
        The user_id (Keycloak UUID) from the 'sub' claim

    Raises:
        AssertionError: If token cannot be decoded or 'sub' claim is missing
    """
    try:
        claims = jwt.get_unverified_claims(token)
    except Exception as e:
        pytest.fail(f"Failed to decode {token_name}: {e}")

    if "sub" not in claims:
        pytest.fail(
            f"{token_name} missing 'sub' claim. Available claims: {list(claims.keys())}"
        )

    return claims["sub"]


@pytest.fixture
def alice_user_id(alice_token: str) -> str:
    """Extract the actual user_id (sub claim) from alice's JWT token.

    This fixture decodes the JWT token without verification to extract
    the 'sub' claim, which contains the Keycloak user UUID. This is the
    actual user_id that get_current_user will use.

    Use this fixture when setting up SpiceDB relationships for alice
    instead of hardcoding "alice" (the username).

    Args:
        alice_token: Alice's JWT access token from Keycloak

    Returns:
        The user_id (Keycloak UUID) for alice
    """
    return _extract_user_id_from_token(alice_token, "alice_token")


@pytest.fixture
def bob_user_id(bob_token: str) -> str:
    """Extract the actual user_id (sub claim) from bob's JWT token.

    Args:
        bob_token: Bob's JWT access token from Keycloak

    Returns:
        The user_id (Keycloak UUID) for bob
    """
    return _extract_user_id_from_token(bob_token, "bob_token")
