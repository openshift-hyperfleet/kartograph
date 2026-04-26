"""Integration tests for MCP endpoint authentication.

Tests all four scenarios from specs/shared-kernel/tenant-context.spec.md
'MCP Authentication' requirement, targeting the MCP endpoint at /query/mcp
rather than REST endpoints.

Spec scenarios covered:
    1. API key authentication:
       GIVEN valid X-API-Key → tenant resolved from key scope (no X-Tenant-ID needed)
    2. Bearer token fallback:
       GIVEN Bearer token + X-Tenant-ID → JWT validated, tenant from header
    3. Authentication failure:
       GIVEN no valid credentials → 401
    4. Service unavailability:
       GIVEN auth backend unreachable → 503 (unit-level only; documented here)

Marked 'keycloak' because Bearer-token fallback tests require a working OIDC
provider (Keycloak in CI; fake OIDC server in isolated-instance mode).

Run with:
    pytest -m "integration and keycloak" tests/integration/test_mcp_authentication.py
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MCP_URL = "/query/mcp"

# Minimal MCP JSON-RPC initialise body.  The middleware intercepts before the
# MCP app logic runs, so any structurally-plausible POST is enough to probe
# authentication responses.  A 401/503 comes from the middleware; everything
# else (200, 400, 422 …) indicates the middleware let the request through.
_MCP_INIT_BODY = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "clientInfo": {"name": "integration-test", "version": "0.0.1"},
        "protocolVersion": "2024-11-05",
    },
    "id": 1,
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client():
    """Async HTTP test client with full lifespan support."""
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture
async def mcp_api_key_secret(
    async_client: AsyncClient,
    tenant_auth_headers: dict[str, str],
) -> str:
    """Create a short-lived API key for MCP authentication tests.

    Returns the plaintext secret so tests can present it in X-API-Key headers.
    """
    unique_name = f"mcp-auth-test-{uuid.uuid4().hex[:8]}"
    response = await async_client.post(
        "/iam/api-keys",
        json={"name": unique_name, "expires_in_days": 1},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 201, (
        f"Failed to create API key for MCP auth test: {response.text}"
    )
    return response.json()["secret"]


# ---------------------------------------------------------------------------
# Scenario: API key authentication
# ---------------------------------------------------------------------------


class TestMCPApiKeyAuthentication:
    """Scenario: API key authentication.

    GIVEN an MCP request with a valid X-API-Key header
    WHEN the request is authenticated
    THEN the tenant is resolved from the API key's tenant scope (no header needed)
    AND the auth context is set for downstream MCP tools
    """

    @pytest.mark.asyncio
    async def test_valid_api_key_passes_auth_gate(
        self,
        async_client: AsyncClient,
        mcp_api_key_secret: str,
    ) -> None:
        """X-API-Key with a valid secret must not be rejected by the auth gate.

        The MCPApiKeyAuthMiddleware resolves the tenant from the API key's
        tenant scope and forwards to the MCP app.  The MCP app may return any
        status code; what matters is that the middleware itself does NOT
        return 401 or 403.
        """
        response = await async_client.post(
            _MCP_URL,
            json=_MCP_INIT_BODY,
            headers={"X-API-Key": mcp_api_key_secret},
        )
        assert response.status_code not in (401, 403), (
            f"Expected auth to succeed but middleware returned {response.status_code}: "
            f"{response.text}"
        )

    @pytest.mark.asyncio
    async def test_api_key_resolves_tenant_without_x_tenant_id_header(
        self,
        async_client: AsyncClient,
        mcp_api_key_secret: str,
    ) -> None:
        """Spec: 'tenant is resolved from the API key's tenant scope (no header needed)'.

        Unlike JWT Bearer auth, an API key carries its own tenant scope, so
        the X-Tenant-ID request header is not required.
        """
        response = await async_client.post(
            _MCP_URL,
            json=_MCP_INIT_BODY,
            headers={
                "X-API-Key": mcp_api_key_secret,
                # Deliberately omit X-Tenant-ID to verify it is not required.
            },
        )
        assert response.status_code not in (401, 403), (
            f"API key auth should not require X-Tenant-ID; "
            f"middleware returned {response.status_code}: {response.text}"
        )


# ---------------------------------------------------------------------------
# Scenario: Bearer token fallback
# ---------------------------------------------------------------------------


class TestMCPBearerTokenFallback:
    """Scenario: Bearer token fallback.

    GIVEN an MCP request with a Bearer token but no API key
    WHEN the request is authenticated
    THEN the JWT is validated
    AND the tenant is resolved from the X-Tenant-ID header
    """

    @pytest.mark.asyncio
    async def test_bearer_token_with_tenant_id_passes_auth_gate(
        self,
        async_client: AsyncClient,
        tenant_auth_headers: dict[str, str],
    ) -> None:
        """Bearer token + X-Tenant-ID (no API key) must be accepted.

        The MCPApiKeyAuthMiddleware falls back to Bearer token validation when
        X-API-Key is absent.  tenant_auth_headers provides:
            Authorization: Bearer <alice's JWT>
            X-Tenant-ID: <default tenant ULID>
        No X-API-Key header is sent, exercising the fallback path.
        """
        # Ensure we're testing the Bearer fallback path (no API key).
        bearer_only_headers = {
            k: v for k, v in tenant_auth_headers.items() if k != "X-API-Key"
        }
        assert "Authorization" in bearer_only_headers, (
            "tenant_auth_headers must include an Authorization Bearer header"
        )
        assert "X-Tenant-ID" in bearer_only_headers, (
            "tenant_auth_headers must include an X-Tenant-ID header"
        )

        response = await async_client.post(
            _MCP_URL,
            json=_MCP_INIT_BODY,
            headers=bearer_only_headers,
        )
        assert response.status_code not in (401, 403), (
            f"Bearer token fallback failed: middleware returned "
            f"{response.status_code}: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_bearer_without_x_tenant_id_handled_gracefully(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Bearer token without X-Tenant-ID should not crash the middleware.

        In multi-tenant mode the tenant context dependency would reject this
        with 400, but at the middleware layer the auth check itself must not
        raise an unhandled exception.  The response may be 401 (if SpiceDB
        check fails due to missing tenant) or 200 (if single-tenant mode
        auto-resolves); either is acceptable at this layer.
        """
        response = await async_client.post(
            _MCP_URL,
            json=_MCP_INIT_BODY,
            headers={"Authorization": auth_headers["Authorization"]},
        )
        # The middleware must not return 500 — it must handle the case cleanly.
        assert response.status_code != 500, (
            f"Middleware raised 500 for Bearer without X-Tenant-ID: {response.text}"
        )


# ---------------------------------------------------------------------------
# Scenario: Authentication failure
# ---------------------------------------------------------------------------


class TestMCPAuthenticationFailure:
    """Scenario: Authentication failure.

    GIVEN an MCP request with no valid credentials
    WHEN the request is authenticated
    THEN a 401 response is returned
    """

    @pytest.mark.asyncio
    async def test_missing_all_credentials_returns_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """No auth headers → 401.

        Spec: 'GIVEN an MCP request with no valid credentials
               WHEN the request is authenticated
               THEN a 401 response is returned'
        """
        response = await async_client.post(
            _MCP_URL,
            json=_MCP_INIT_BODY,
        )
        assert response.status_code == 401, (
            f"Expected 401 for missing credentials, got {response.status_code}: "
            f"{response.text}"
        )

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unrecognised API key secret → 401."""
        response = await async_client.post(
            _MCP_URL,
            json=_MCP_INIT_BODY,
            headers={"X-API-Key": "karto_this_key_does_not_exist_in_the_database"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_without_api_key_returns_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Malformed JWT + X-Tenant-ID (no API key) → 401."""
        response = await async_client.post(
            _MCP_URL,
            json=_MCP_INIT_BODY,
            headers={
                "Authorization": "Bearer this.is.not.a.valid.jwt.token",
                "X-Tenant-ID": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_401_response_includes_www_authenticate_header(
        self,
        async_client: AsyncClient,
    ) -> None:
        """401 responses must include a WWW-Authenticate header.

        The MCPApiKeyAuthMiddleware sends 'ApiKey realm="kartograph"'.
        This allows API clients to discover that API key auth is accepted.
        """
        response = await async_client.post(
            _MCP_URL,
            json=_MCP_INIT_BODY,
        )
        assert response.status_code == 401
        lower_headers = {k.lower(): v for k, v in response.headers.items()}
        assert "www-authenticate" in lower_headers, (
            "401 response from MCP auth gate must include WWW-Authenticate"
        )


# ---------------------------------------------------------------------------
# Scenario: Service unavailability (documented; unit-level coverage)
# ---------------------------------------------------------------------------


class TestMCPServiceUnavailability:
    """Scenario: Service unavailability.

    GIVEN an MCP request when the authentication backend is unreachable
    WHEN the request is authenticated
    THEN a 503 response is returned

    This scenario is fully covered at the unit level:
        tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py
        :: TestMCPApiKeyAuthMiddlewareValidationError
        :: test_returns_503_when_validator_raises

    At integration level, simulating a database outage mid-request requires
    stopping the database between sending the request and the middleware
    executing the validation query, which is impractical in an in-process
    ASGI test.  The unit test provides strong confidence because it exercises
    the exact exception-handling code path in MCPApiKeyAuthMiddleware.
    """

    @pytest.mark.skip(
        reason=(
            "503 behaviour is fully covered by unit tests: "
            "test_mcp_auth_middleware.py::"
            "TestMCPApiKeyAuthMiddlewareValidationError::"
            "test_returns_503_when_validator_raises. "
            "Simulating a database outage in an in-process ASGI integration "
            "test is impractical."
        )
    )
    @pytest.mark.asyncio
    async def test_503_when_auth_backend_unreachable(
        self,
        async_client: AsyncClient,
    ) -> None:
        """503 is returned when the API key validation backend (DB) is unreachable."""
        # Covered at unit level; placeholder kept for spec traceability.
