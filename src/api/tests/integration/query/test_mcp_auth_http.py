"""HTTP-level integration tests for MCP no-credentials and invalid-key 401 responses.

Verifies that MCPApiKeyAuthMiddleware correctly enforces authentication at the
HTTP transport layer, returning 401 before the inner MCP app is reached.

These are raw HTTP tests — not MCP protocol tests via ``fastmcp.Client``.
The goal is to verify ASGI middleware behaviour at the HTTP response layer,
not the tool-call response format.

Why this test exists
--------------------
The middleware unit test (``test_mcp_auth_wiring.py``) only asserts that
``query_mcp_app`` is an instance of ``MCPApiKeyAuthMiddleware``.  It does NOT
verify the 401 HTTP response when credentials are absent or invalid.

A regression in ``MCPApiKeyAuthMiddleware.__call__`` that accidentally calls the
inner app before authentication (allowing unauthenticated access) would go
undetected by the existing test suite until a security review or production
incident.  This file fills that gap.

Spec coverage
-------------
specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e:
  - Requirement: MCP Authentication
  - Scenario: No credentials
    "GIVEN a request with no authentication headers
     WHEN the MCP request is processed
     THEN a 401 response is returned"

Note: ``@pytest.mark.keycloak`` is intentionally NOT applied.
These tests exercise the no-credentials path (before any OIDC interaction) and
the invalid-API-key path (which only requires PostgreSQL for the DB lookup).
Both paths run against a standard ``make instance-up`` environment.

Run with:
    make instance-up
    source .instances/$(basename $(pwd))/.env.instance
    cd src/api && uv run pytest tests/integration/query/test_mcp_auth_http.py \\
        -v -m integration

Regression validation (no-credentials test):
  1. In ``MCPApiKeyAuthMiddleware.__call__``, remove the final
     ``await self._send_json_error(send, 401, "X-API-Key header is required")``
     (or replace it with a pass to the inner app).
  2. ``test_no_credentials_returns_401`` MUST fail (response will be 200 or 500,
     not 401).
  3. Restore the line — all tests pass.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client with full app lifespan.

    Starts the Kartograph application (including MCP server lifespan) in-process
    via ``LifespanManager``.  No Keycloak is required — the tests exercise the
    pre-authentication middleware paths only.
    """
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# ---------------------------------------------------------------------------
# Tests — no credentials
# ---------------------------------------------------------------------------


class TestMCPAuthenticationNoCredentials:
    """HTTP-level tests for the MCP no-credentials 401 scenario.

    Spec: specs/query/mcp-server.spec.md
      Requirement: MCP Authentication
      Scenario: No credentials
        "GIVEN a request with no authentication headers
         WHEN the MCP request is processed
         THEN a 401 response is returned"

    The ``MCPApiKeyAuthMiddleware`` implements this at line:
    ``await self._send_json_error(send, 401, "X-API-Key header is required")``
    in the 'neither auth method present' branch.
    """

    @pytest.mark.asyncio
    async def test_no_credentials_returns_401(self, async_client: AsyncClient) -> None:
        """POST /query/mcp with no auth headers MUST return 401.

        Spec: Scenario: No credentials —
        "GIVEN a request with no authentication headers
         WHEN the MCP request is processed
         THEN a 401 response is returned"

        A regression that accidentally passes requests through to the inner app
        before authentication would return 200 or 400, making this test fail.
        """
        response = await async_client.post("/query/mcp")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_credentials_response_body_contains_error_field(
        self, async_client: AsyncClient
    ) -> None:
        """No-credentials 401 response body MUST be JSON with a non-empty 'error' field.

        Confirms a structured error response (not a crash or empty body).
        The middleware uses ``_send_json_error`` which produces:
        ``{"error": "X-API-Key header is required"}``
        """
        response = await async_client.post("/query/mcp")

        assert response.status_code == 401

        body = response.json()
        assert "error" in body, (
            f"Expected 'error' key in response body, got: {list(body.keys())}"
        )
        assert isinstance(body["error"], str), (
            f"Expected 'error' to be a string, got: {type(body['error'])}"
        )
        assert len(body["error"]) > 0, "Expected non-empty 'error' message"

    @pytest.mark.asyncio
    async def test_no_credentials_response_includes_www_authenticate_header(
        self, async_client: AsyncClient
    ) -> None:
        """No-credentials 401 MUST include a WWW-Authenticate header.

        Per RFC 9110 §11.6.1, 401 responses should include a WWW-Authenticate
        header indicating the accepted authentication scheme.
        ``MCPApiKeyAuthMiddleware._send_json_error`` appends this header for
        all 401 responses.
        """
        response = await async_client.post("/query/mcp")

        assert response.status_code == 401
        assert "www-authenticate" in response.headers, (
            "Expected 'WWW-Authenticate' header in 401 response (RFC 9110 §11.6.1)"
        )

    @pytest.mark.asyncio
    async def test_get_request_without_credentials_returns_401(
        self, async_client: AsyncClient
    ) -> None:
        """GET /query/mcp without auth MUST also return 401.

        The middleware runs before MCP protocol parsing, so any HTTP method
        exercises the auth check.  Verifies the auth gate is method-agnostic.
        """
        response = await async_client.get("/query/mcp")

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests — invalid API key
# ---------------------------------------------------------------------------


class TestMCPAuthenticationInvalidApiKey:
    """HTTP-level tests for the MCP invalid-API-key 401 response.

    Requires PostgreSQL to be running (``make instance-up``) so that
    ``validate_mcp_api_key`` can query the database and return ``None``
    for an unknown key.

    Spec: specs/query/mcp-server.spec.md
      Requirement: MCP Authentication
      Scenario: Invalid API key

    Implementation note: DB-backed tests are combined into a single test
    method to avoid asyncpg event-loop isolation issues that arise when
    ``LifespanManager`` (and its DB connection pools) are torn down and
    recreated across separate ``async_client`` fixture instances within the
    same pytest session.
    """

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401_with_structured_error(
        self, async_client: AsyncClient
    ) -> None:
        """Request with invalid X-API-Key MUST return 401 with a structured JSON body.

        ``MCPApiKeyAuthMiddleware`` validates the key against PostgreSQL;
        when the lookup returns ``None`` (key not found / revoked), it calls
        ``_send_json_error(send, 401, "Invalid or expired API key")``.

        Asserts in a single round-trip:
        1. Response status is 401.
        2. Response body is JSON with a non-empty ``error`` field (structured
           error, not a stack trace or crash dump).

        A regression that skips the DB validation step would return 200/400
        instead of 401, making this test fail.  A regression that leaks
        implementation details would fail the body assertions.
        """
        response = await async_client.post(
            "/query/mcp",
            headers={"X-API-Key": "invalid-garbage-key-that-does-not-exist"},
        )

        assert response.status_code == 401

        body = response.json()
        assert "error" in body, (
            f"Expected 'error' key in response body, got: {list(body.keys())}"
        )
        assert isinstance(body["error"], str), (
            f"Expected 'error' to be a string, got: {type(body['error'])}"
        )
        assert len(body["error"]) > 0, "Expected non-empty 'error' message"
