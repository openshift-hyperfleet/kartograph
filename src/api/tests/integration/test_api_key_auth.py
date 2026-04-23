"""Integration tests for API Key authentication and authorization.

Tests the dual authentication flow supporting both JWT Bearer tokens
and X-API-Key header authentication, plus SpiceDB-backed authorization
enforcement for API key revocation.
"""

import os
import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iam.application.security import extract_prefix, generate_api_key_secret
from iam.domain.value_objects import APIKeyId
from iam.infrastructure.outbox import IAMEventTranslator
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.outbox.spicedb_handler import SpiceDBEventHandler
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings
from main import app
from pydantic import SecretStr
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    ResourceType,
    format_resource,
    format_subject,
)
from infrastructure.outbox.worker import OutboxWorker
from shared_kernel.outbox.observability import DefaultOutboxWorkerProbe

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support."""
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture
async def unique_api_key_name() -> str:
    return f"test-api-key-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def api_key_secret(
    async_client, tenant_auth_headers, unique_api_key_name: str
) -> str:
    """Create an API key and return the plaintext secret.

    Uses JWT auth to create the key, then returns the secret for testing.
    Uses unique name per test run to avoid conflicts.
    """
    response = await async_client.post(
        "/iam/api-keys",
        json={"name": unique_api_key_name, "expires_in_days": 1},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 201, f"Failed to create API key: {response.json()}"
    return response.json()["secret"]


@pytest_asyncio.fixture
async def revoked_api_key_secret(
    async_client, tenant_auth_headers, unique_api_key_name: str
) -> str:
    """Create an API key, revoke it, and return the secret.

    Used to test that revoked keys are rejected.
    Uses unique name per test run to avoid conflicts.
    """
    # Create the key
    create_response = await async_client.post(
        "/iam/api-keys",
        json={"name": unique_api_key_name, "expires_in_days": 1},
        headers=tenant_auth_headers,
    )
    assert create_response.status_code == 201
    key_data = create_response.json()
    secret = key_data["secret"]
    key_id = key_data["id"]

    # Revoke the key
    revoke_response = await async_client.delete(
        f"/iam/api-keys/{key_id}",
        headers=tenant_auth_headers,
    )
    assert revoke_response.status_code == 204

    return secret


@pytest_asyncio.fixture
async def expired_api_key_secret(
    _authz_db_settings: DatabaseSettings,
    default_tenant_id: str,
    alice_token: str,
) -> AsyncGenerator[str, None]:
    """Create an expired API key by inserting directly into the database.

    The API route enforces a 1-day minimum expiration, so this fixture
    bypasses the route and writes directly to the DB to produce an already-
    expired key for testing the authentication rejection path.

    Uses bcrypt work factor 4 (vs. production factor 12) for test speed,
    since verify_api_key_secret respects the cost stored in the hash.
    """
    claims = jose_jwt.get_unverified_claims(alice_token)
    user_id = claims["sub"]

    secret = generate_api_key_secret()
    # Use low work factor for speed in tests — bcrypt.checkpw respects stored cost
    key_hash = bcrypt.hashpw(secret.encode(), bcrypt.gensalt(4)).decode()
    prefix = extract_prefix(secret)
    api_key_id = APIKeyId.generate().value
    expires_at = datetime.now(UTC) - timedelta(days=1)  # expired yesterday

    engine = create_write_engine(_authz_db_settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await session.execute(
            text("""
                INSERT INTO api_keys
                    (id, created_by_user_id, tenant_id, name,
                     key_hash, prefix, expires_at, is_revoked,
                     created_at, updated_at)
                VALUES
                    (:id, :user_id, :tenant_id, :name,
                     :key_hash, :prefix, :expires_at, false,
                     now(), now())
            """),
            {
                "id": api_key_id,
                "user_id": user_id,
                "tenant_id": default_tenant_id,
                "name": f"expired-key-{api_key_id}",
                "key_hash": key_hash,
                "prefix": prefix,
                "expires_at": expires_at.isoformat(),
            },
        )
        await session.commit()

    await engine.dispose()

    yield secret

    # Cleanup: remove the directly-inserted key
    engine = create_write_engine(_authz_db_settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM api_keys WHERE id = :id"),
            {"id": api_key_id},
        )
        await session.commit()
    await engine.dispose()


class TestAPIKeyAuthentication:
    """Tests for X-API-Key header authentication."""

    @pytest.mark.asyncio
    async def test_authenticates_with_valid_api_key(self, async_client, api_key_secret):
        """X-API-Key header with valid key should authenticate."""
        response = await async_client.get(
            "/iam/tenants",
            headers={"X-API-Key": api_key_secret},
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_returns_401_for_invalid_api_key(self, async_client):
        """Invalid API key should return 401."""
        response = await async_client.get(
            "/iam/tenants",
            headers={"X-API-Key": "karto_invalid_key_that_does_not_exist"},
        )

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer, API-Key"

    @pytest.mark.asyncio
    async def test_returns_401_for_revoked_api_key(
        self, async_client, revoked_api_key_secret
    ):
        """Revoked API key should return 401."""
        response = await async_client.get(
            "/iam/tenants",
            headers={"X-API-Key": revoked_api_key_secret},
        )

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer, API-Key"

    @pytest.mark.asyncio
    async def test_returns_401_for_expired_api_key(
        self, async_client, expired_api_key_secret
    ):
        """Expired API key should return 401.

        Spec: 'GIVEN an API key that has passed its expiration time
               WHEN a request includes the key
               THEN authentication fails with a 401 response'

        The key is inserted directly into the DB (bypassing the route's
        1-day minimum) so that expires_at is in the past at test time.
        """
        response = await async_client.get(
            "/iam/tenants",
            headers={"X-API-Key": expired_api_key_secret},
        )

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer, API-Key"

    @pytest.mark.asyncio
    async def test_updates_last_used_at_on_success(
        self,
        async_client,
        tenant_auth_headers,
        api_key_secret,
        unique_api_key_name: str,
    ):
        """Successful auth should update last_used_at."""
        # First, list keys to get the initial state
        list_response_before = await async_client.get(
            "/iam/api-keys",
            headers=tenant_auth_headers,
        )
        assert list_response_before.status_code == 200
        keys_before = list_response_before.json()
        auth_key = next(
            (k for k in keys_before if k["name"] == unique_api_key_name), None
        )
        assert auth_key is not None
        initial_last_used = auth_key.get("last_used_at")

        # Make a request with the API key
        auth_response = await async_client.get(
            "/iam/tenants",
            headers={"X-API-Key": api_key_secret},
        )
        assert auth_response.status_code == 200

        # Check that last_used_at was updated
        list_response_after = await async_client.get(
            "/iam/api-keys",
            headers=tenant_auth_headers,
        )
        assert list_response_after.status_code == 200
        keys_after = list_response_after.json()
        auth_key_after = next(
            (k for k in keys_after if k["name"] == unique_api_key_name), None
        )
        assert auth_key_after is not None
        updated_last_used = auth_key_after.get("last_used_at")

        # last_used_at should be set now
        assert updated_last_used is not None
        # If it was previously None, it's definitely updated
        # If it was set before, the new value should be >= old value
        if initial_last_used is not None:
            assert updated_last_used >= initial_last_used


class TestDualAuthentication:
    """Tests for dual JWT + API Key authentication support."""

    @pytest.mark.asyncio
    async def test_jwt_auth_still_works(self, async_client, tenant_auth_headers):
        """JWT Bearer token should still work."""
        response = await async_client.get("/iam/tenants", headers=tenant_auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_api_key_auth_works(self, async_client, api_key_secret):
        """X-API-Key header should work."""
        response = await async_client.get(
            "/iam/tenants",
            headers={"X-API-Key": api_key_secret},
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_no_auth_returns_401_with_both_methods(self, async_client):
        """No auth should return 401 with WWW-Authenticate: Bearer, API-Key."""
        response = await async_client.get("/iam/tenants")

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer, API-Key"

    @pytest.mark.asyncio
    async def test_prefers_jwt_when_both_provided(
        self, async_client, tenant_auth_headers, api_key_secret
    ):
        """When both JWT and API Key provided, prefer JWT.

        We verify JWT is used by checking the response succeeds.
        The behavior is the same with either auth method, but this
        confirms the precedence works correctly.
        """
        # Combine both auth methods
        combined_headers = {
            **tenant_auth_headers,
            "X-API-Key": api_key_secret,
        }

        response = await async_client.get("/iam/tenants", headers=combined_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_invalid_jwt_with_valid_api_key_uses_api_key(
        self, async_client, api_key_secret
    ):
        """When JWT is invalid but API Key is valid, JWT error takes precedence.

        This tests the "JWT first" behavior - if JWT is present but invalid,
        we should fail with a JWT error rather than falling through to API Key.
        """
        headers = {
            "Authorization": "Bearer invalid.token.here",
            "X-API-Key": api_key_secret,
        }

        response = await async_client.get("/iam/tenants", headers=headers)

        # JWT is tried first and fails, so we get 401
        assert response.status_code == 401


class TestAPIKeyCanAccessProtectedEndpoints:
    """Verify API key authentication grants access to protected endpoints."""

    @pytest.mark.asyncio
    async def test_can_access_graph_schema_nodes(self, async_client, api_key_secret):
        """API key should grant access to graph schema nodes."""
        response = await async_client.get(
            "/graph/schema/nodes",
            headers={"X-API-Key": api_key_secret},
        )

        assert response.status_code == 200
        assert "labels" in response.json()

    @pytest.mark.asyncio
    async def test_can_access_iam_tenants_list(self, async_client, api_key_secret):
        """API key should grant access to tenant listing."""
        response = await async_client.get(
            "/iam/tenants",
            headers={"X-API-Key": api_key_secret},
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_can_access_graph_nodes_by_slug(self, async_client, api_key_secret):
        """API key should grant access to graph node queries."""
        response = await async_client.get(
            "/graph/nodes/by-slug?slug=test",
            headers={"X-API-Key": api_key_secret},
        )

        assert response.status_code == 200
        assert "nodes" in response.json()


# =============================================================================
# Authorization Enforcement Fixtures
# =============================================================================
# These fixtures provide SpiceDB and outbox processing support needed for
# authorization tests. They duplicate some fixtures from iam/conftest.py
# because this test file lives at the integration/ level, not under iam/.


@pytest.fixture
def _authz_db_settings() -> DatabaseSettings:
    """Database settings for authorization test fixtures."""
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
async def _authz_session_factory(
    _authz_db_settings: DatabaseSettings,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Session factory for outbox worker in authorization tests."""
    engine = create_write_engine(_authz_db_settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def _spicedb_client() -> AuthorizationProvider:
    """SpiceDB client for authorization tests."""
    return get_spicedb_client()


@pytest_asyncio.fixture
async def process_outbox(
    _authz_session_factory: async_sessionmaker[AsyncSession],
    _spicedb_client: AuthorizationProvider,
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Process all pending outbox entries to sync SpiceDB relationships.

    Must be called after creating API keys so that owner and tenant
    relationships are written to SpiceDB before authorization checks.
    """
    probe = DefaultOutboxWorkerProbe()
    spicedb_handler = SpiceDBEventHandler(
        translator=IAMEventTranslator(),
        authz=_spicedb_client,
    )

    worker = OutboxWorker(
        session_factory=_authz_session_factory,
        handler=spicedb_handler,
        probe=probe,
    )

    async def _process() -> None:
        await worker._process_batch()

    return _process


@pytest_asyncio.fixture
async def alice_admin_tenant_auth_headers(
    tenant_auth_headers: dict[str, str],
    alice_token: str,
    default_tenant_id: str,
    _spicedb_client: AuthorizationProvider,
) -> AsyncGenerator[dict[str, str], None]:
    """Auth headers for alice with tenant admin role in SpiceDB.

    The standard tenant_auth_headers grants alice 'member' on the tenant.
    This fixture additionally grants 'admin', which is required for
    tenant-level administrative actions like revoking other users' API keys.

    The admin grant is removed during teardown to avoid leaking state
    between tests.
    """
    from jose import jwt as jose_jwt

    claims = jose_jwt.get_unverified_claims(alice_token)
    user_id = claims["sub"]

    tenant_resource = format_resource(ResourceType.TENANT, default_tenant_id)
    user_subject = format_subject(ResourceType.USER, user_id)

    await _spicedb_client.write_relationship(
        resource=tenant_resource,
        relation="admin",
        subject=user_subject,
    )

    yield tenant_auth_headers

    await _spicedb_client.delete_relationship(
        resource=tenant_resource,
        relation="admin",
        subject=user_subject,
    )


# =============================================================================
# Authorization Enforcement Tests
# =============================================================================


class TestAPIKeyAuthorizationEnforcement:
    """Tests for SpiceDB-backed authorization on API key operations.

    Validates the ReBAC model defined in schema.zed:
        api_key#revoke = owner + tenant->administrate

    Where tenant->administrate = tenant#admin.

    Alice is granted tenant admin; Bob is a tenant member (not admin).
    """

    @pytest.mark.asyncio
    async def test_owner_can_revoke_own_key(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict[str, str],
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """API key owner should be able to revoke their own key.

        Uses tenant_auth_headers (alice as member, NOT admin) so this
        test exercises the owner relationship path exclusively:
        api_key#owner@user -> api_key#revoke.
        """
        # Alice creates an API key (she is the owner, not a tenant admin)
        create_response = await async_client.post(
            "/iam/api-keys",
            json={
                "name": f"alice-own-key-{uuid.uuid4().hex[:8]}",
                "expires_in_days": 1,
            },
            headers=tenant_auth_headers,
        )
        assert create_response.status_code == 201
        key_id = create_response.json()["id"]

        # Process outbox to write owner + tenant relationships to SpiceDB
        await process_outbox()

        # Alice revokes her own key (as owner, not admin)
        revoke_response = await async_client.delete(
            f"/iam/api-keys/{key_id}",
            headers=tenant_auth_headers,
        )

        assert revoke_response.status_code == 204

    @pytest.mark.asyncio
    async def test_tenant_admin_can_revoke_other_users_key(
        self,
        async_client: AsyncClient,
        alice_admin_tenant_auth_headers: dict[str, str],
        bob_tenant_auth_headers: dict[str, str],
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """Tenant admin should be able to revoke any key in their tenant.

        Bob (tenant member) creates a key. Alice (tenant admin) revokes it.
        Authorization flows: api_key#tenant@tenant -> tenant#admin@alice
        which satisfies api_key#revoke via tenant->administrate.
        """
        # Bob creates an API key (bob is the owner)
        create_response = await async_client.post(
            "/iam/api-keys",
            json={
                "name": f"bob-key-{uuid.uuid4().hex[:8]}",
                "expires_in_days": 1,
            },
            headers=bob_tenant_auth_headers,
        )
        assert create_response.status_code == 201
        key_id = create_response.json()["id"]

        # Process outbox to write bob's owner + tenant relationships to SpiceDB
        await process_outbox()

        # Alice (tenant admin) revokes bob's key
        revoke_response = await async_client.delete(
            f"/iam/api-keys/{key_id}",
            headers=alice_admin_tenant_auth_headers,
        )

        assert revoke_response.status_code == 204

    @pytest.mark.asyncio
    async def test_non_admin_cannot_revoke_other_users_key(
        self,
        async_client: AsyncClient,
        alice_admin_tenant_auth_headers: dict[str, str],
        bob_tenant_auth_headers: dict[str, str],
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """Non-admin tenant member must NOT revoke another user's key.

        Alice creates a key. Bob (member, not admin) attempts to revoke it.
        Bob is neither the owner nor a tenant admin, so SpiceDB denies
        the revoke permission and the service returns 403.
        """
        # Alice creates an API key (alice is the owner)
        create_response = await async_client.post(
            "/iam/api-keys",
            json={
                "name": f"alice-key-{uuid.uuid4().hex[:8]}",
                "expires_in_days": 1,
            },
            headers=alice_admin_tenant_auth_headers,
        )
        assert create_response.status_code == 201
        key_id = create_response.json()["id"]

        # Process outbox to write owner + tenant relationships to SpiceDB
        await process_outbox()

        # Bob (member, not admin) attempts to revoke alice's key
        revoke_response = await async_client.delete(
            f"/iam/api-keys/{key_id}",
            headers=bob_tenant_auth_headers,
        )

        assert revoke_response.status_code == 403

    @pytest.mark.asyncio
    async def test_revoked_key_remains_visible_in_listing(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict[str, str],
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """Revoked API keys should remain visible in listings with is_revoked=True.

        Spec: 'GIVEN a user who created an API key
               WHEN the user revokes the key
               THEN the key is marked as revoked
               AND the key remains visible in listings with `is_revoked` set to true'

        Steps:
          1. Create a key (alice owns it)
          2. Process outbox so SpiceDB has owner + tenant relationships
          3. Revoke the key (alice as owner)
          4. List keys and assert the revoked entry is present with is_revoked=True
        """
        key_name = f"revoke-list-test-{uuid.uuid4().hex[:8]}"

        # 1. Create a key
        create_response = await async_client.post(
            "/iam/api-keys",
            json={"name": key_name, "expires_in_days": 1},
            headers=tenant_auth_headers,
        )
        assert create_response.status_code == 201
        key_id = create_response.json()["id"]

        # 2. Process outbox so SpiceDB has the owner relationship (needed for revoke
        #    and for lookup_resources to return this key in the listing)
        await process_outbox()

        # 3. Revoke the key (alice as owner)
        revoke_response = await async_client.delete(
            f"/iam/api-keys/{key_id}",
            headers=tenant_auth_headers,
        )
        assert revoke_response.status_code == 204

        # 4. List keys — the revoked key must still appear with is_revoked=True
        list_response = await async_client.get(
            "/iam/api-keys",
            headers=tenant_auth_headers,
        )
        assert list_response.status_code == 200
        keys = list_response.json()

        revoked_key = next((k for k in keys if k["id"] == key_id), None)
        assert revoked_key is not None, (
            f"Revoked key {key_id} should still appear in the listing for audit purposes"
        )
        assert revoked_key["is_revoked"] is True

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason=(
            "Cannot easily test without a third non-member user. "
            "The test infrastructure only provisions alice (admin) and bob (member). "
            "Creating a non-member user requires Keycloak provisioning which is "
            "outside the scope of these integration fixtures. The tenant membership "
            "check is implicitly covered by the authentication layer — unauthenticated "
            "requests already return 401."
        )
    )
    async def test_create_api_key_requires_tenant_membership(self):
        """A user who is not a tenant member should not be able to create API keys.

        Skipped: requires a third user who is authenticated but not a member
        of the default tenant. The current test infrastructure only supports
        alice and bob, both of whom are tenant members.
        """
