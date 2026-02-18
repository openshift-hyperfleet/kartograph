"""Integration test fixtures for IAM bounded context.

These fixtures require running PostgreSQL and SpiceDB instances.
SpiceDB settings are configured in the parent conftest.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
import os
import time
from typing import TYPE_CHECKING, Any, cast

from jose import jwt
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import CursorResult, text
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
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from shared_kernel.outbox.observability import DefaultOutboxWorkerProbe

if TYPE_CHECKING:
    from httpx import AsyncClient
from tests.integration.iam.cleanup_probe import DefaultTestCleanupProbe


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
) -> AsyncGenerator[None, None]:
    """Clean IAM tables and SpiceDB relationships before and after tests.

    Deletes test data while preserving the default tenant and its root workspace.
    Uses domain probe for observability instead of direct logging.

    Deletion order respects FK constraints:
    outbox -> api_keys -> groups -> users -> workspaces (children) ->
    workspaces (roots) -> tenants
    """
    default_tenant_name = get_iam_settings().default_tenant_name
    probe = DefaultTestCleanupProbe()

    async def cleanup() -> None:
        """Perform cleanup with proper FK constraint ordering."""
        probe.cleanup_started(default_tenant_name=default_tenant_name)

        try:
            # Delete in FK-respecting order
            await async_session.execute(text("DELETE FROM outbox"))
            probe.table_cleaned("outbox")

            await async_session.execute(text("DELETE FROM api_keys"))
            probe.table_cleaned("api_keys")

            await async_session.execute(text("DELETE FROM groups"))
            probe.table_cleaned("groups")

            await async_session.execute(text("DELETE FROM users"))
            probe.table_cleaned("users")

            # Delete workspaces before tenants (RESTRICT FK constraint)
            # Delete child workspaces first (those with parent_workspace_id)
            children_result = cast(
                CursorResult,
                await async_session.execute(
                    text("DELETE FROM workspaces WHERE parent_workspace_id IS NOT NULL")
                ),
            )
            probe.table_cleaned("workspaces (children)", children_result.rowcount)

            # Delete remaining workspaces (root workspaces) except default tenant's
            roots_result = cast(
                CursorResult,
                await async_session.execute(
                    text("""
                        DELETE FROM workspaces
                        WHERE tenant_id IN (
                            SELECT id FROM tenants WHERE name != :default_name
                        )
                    """),
                    {"default_name": default_tenant_name},
                ),
            )
            probe.table_cleaned("workspaces (roots)", roots_result.rowcount)

            # Now safe to delete tenants
            tenants_result = cast(
                CursorResult,
                await async_session.execute(
                    text("DELETE FROM tenants WHERE name != :default_name"),
                    {"default_name": default_tenant_name},
                ),
            )
            probe.table_cleaned("tenants", tenants_result.rowcount)

            await async_session.commit()
            probe.cleanup_completed(tables_cleaned=7)

        except Exception as e:
            probe.cleanup_failed(table_name="unknown", error=str(e))
            await async_session.rollback()
            raise  # Re-raise to make test failures visible

    # Clean before test
    await cleanup()

    yield

    # Clean after test
    await cleanup()


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


@pytest.fixture
def grant_workspace_admin(
    spicedb_client: AuthorizationProvider,
    alice_user_id: str,
) -> Callable[[str], Coroutine[Any, Any, None]]:
    """Provide a function to grant Alice admin on a workspace in SpiceDB.

    The workspace service now emits a WorkspaceMemberAdded event granting
    the creator admin access. However, outbox events are processed
    asynchronously, so SpiceDB relationships are not available immediately
    after the API call returns.

    This fixture writes the admin relationship to SpiceDB synchronously
    so that subsequent operations (create children, delete) succeed
    permission checks without waiting for outbox processing.

    Usage:
        workspace = resp.json()
        await grant_workspace_admin(workspace["id"])
    """

    async def _grant(workspace_id: str) -> None:
        resource = format_resource(ResourceType.WORKSPACE, workspace_id)
        subject = format_subject(ResourceType.USER, alice_user_id)

        await spicedb_client.write_relationship(
            resource=resource,
            relation="admin",
            subject=subject,
        )

    return _grant


async def wait_for_permission(
    authz: AuthorizationProvider,
    resource: str,
    permission: str,
    subject: str,
    timeout: float = 5.0,
    poll_interval: float = 0.05,
) -> bool:
    """Wait for a permission to become available in SpiceDB.

    The outbox pattern introduces eventual consistency between PostgreSQL
    and SpiceDB. This helper waits for the outbox worker to process events
    and write relationships to SpiceDB before proceeding with assertions.

    Args:
        authz: Authorization provider (SpiceDB client)
        resource: Resource identifier (e.g., "group:123")
        permission: Permission to check (e.g., "manage")
        subject: Subject identifier (e.g., "user:456")
        timeout: Maximum time to wait in seconds
        poll_interval: Time between checks in seconds

    Returns:
        True if permission became available, False if timeout exceeded
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if await authz.check_permission(resource, permission, subject):
            return True
        await asyncio.sleep(poll_interval)
    return False


async def create_child_workspace(
    async_client: AsyncClient,
    tenant_auth_headers: dict,
    spicedb_client: AuthorizationProvider,
    alice_user_id: str,
    name: str = "test_ws",
) -> str:
    """Create a child workspace under the root and wait for admin permission.

    Shared helper for integration tests that need a child workspace.

    Returns the workspace ID.
    """
    ws_list = await async_client.get("/iam/workspaces", headers=tenant_auth_headers)
    assert ws_list.status_code == 200, f"Failed to list workspaces: {ws_list.text}"
    root = next(w for w in ws_list.json()["workspaces"] if w["is_root"])

    create_resp = await async_client.post(
        "/iam/workspaces",
        headers=tenant_auth_headers,
        json={"name": name, "parent_workspace_id": root["id"]},
    )
    assert create_resp.status_code == 201, (
        f"Failed to create workspace: {create_resp.text}"
    )
    ws_id = create_resp.json()["id"]

    ws_resource = format_resource(ResourceType.WORKSPACE, ws_id)
    alice_subject = format_subject(ResourceType.USER, alice_user_id)
    admin_ready = await wait_for_permission(
        spicedb_client,
        resource=ws_resource,
        permission=Permission.MANAGE,
        subject=alice_subject,
        timeout=5.0,
    )
    assert admin_ready, "Timed out waiting for workspace admin permission"

    return ws_id


async def create_group(
    async_client: AsyncClient,
    tenant_auth_headers: dict,
    spicedb_client: AuthorizationProvider,
    alice_user_id: str,
    name: str = "test_group",
) -> str:
    """Create a group and wait for admin permission.

    Shared helper for integration tests that need a group.

    Returns the group ID.
    """
    create_resp = await async_client.post(
        "/iam/groups",
        headers=tenant_auth_headers,
        json={"name": name},
    )
    assert create_resp.status_code == 201, f"Failed to create group: {create_resp.text}"
    group_id = create_resp.json()["id"]

    group_resource = format_resource(ResourceType.GROUP, group_id)
    alice_subject = format_subject(ResourceType.USER, alice_user_id)
    admin_ready = await wait_for_permission(
        spicedb_client,
        resource=group_resource,
        permission=Permission.MANAGE,
        subject=alice_subject,
        timeout=5.0,
    )
    assert admin_ready, "Timed out waiting for group admin permission"

    return group_id
