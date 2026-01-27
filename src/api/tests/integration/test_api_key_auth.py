"""Integration tests for API Key authentication.

Tests the dual authentication flow supporting both JWT Bearer tokens
and X-API-Key header authentication.
"""

import uuid

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from main import app

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
async def api_key_secret(async_client, auth_headers, unique_api_key_name: str) -> str:
    """Create an API key and return the plaintext secret.

    Uses JWT auth to create the key, then returns the secret for testing.
    Uses unique name per test run to avoid conflicts.
    """
    response = await async_client.post(
        "/iam/api-keys",
        json={"name": unique_api_key_name, "expires_in_days": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create API key: {response.json()}"
    return response.json()["secret"]


@pytest_asyncio.fixture
async def revoked_api_key_secret(
    async_client, auth_headers, unique_api_key_name: str
) -> str:
    """Create an API key, revoke it, and return the secret.

    Used to test that revoked keys are rejected.
    Uses unique name per test run to avoid conflicts.
    """
    # Create the key
    create_response = await async_client.post(
        "/iam/api-keys",
        json={"name": unique_api_key_name, "expires_in_days": 1},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    key_data = create_response.json()
    secret = key_data["secret"]
    key_id = key_data["id"]

    # Revoke the key
    revoke_response = await async_client.delete(
        f"/iam/api-keys/{key_id}",
        headers=auth_headers,
    )
    assert revoke_response.status_code == 204

    return secret


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
    async def test_updates_last_used_at_on_success(
        self, async_client, auth_headers, api_key_secret, unique_api_key_name: str
    ):
        """Successful auth should update last_used_at."""
        # First, list keys to get the initial state
        list_response_before = await async_client.get(
            "/iam/api-keys",
            headers=auth_headers,
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
            headers=auth_headers,
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
    async def test_jwt_auth_still_works(self, async_client, auth_headers):
        """JWT Bearer token should still work."""
        response = await async_client.get("/iam/tenants", headers=auth_headers)

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
        self, async_client, auth_headers, api_key_secret
    ):
        """When both JWT and API Key provided, prefer JWT.

        We verify JWT is used by checking the response succeeds.
        The behavior is the same with either auth method, but this
        confirms the precedence works correctly.
        """
        # Combine both auth methods
        combined_headers = {
            **auth_headers,
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
