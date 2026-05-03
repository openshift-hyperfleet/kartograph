"""HTTP-level integration tests for MCP forbidden query response contract.

Tests the full HTTP stack from the MCP HTTP endpoint through to the Cypher
execution safeguards, verifying that forbidden query responses include the
``correlation_id`` field as required by the spec.

Why this test exists
--------------------
The *unit* tests verify each layer in isolation:
- ``test_query_repository.py::test_forbidden_error_has_correlation_id`` — repository
  assigns a correlation_id to QueryForbiddenError.
- ``test_application_services.py::test_forbidden_error_includes_correlation_id_in_response``
  — MCPQueryService preserves correlation_id in the returned QueryError.
- ``test_mcp_query_tool.py::TestBuildErrorResponseForbiddenErrors`` — _build_error_response
  serialises correlation_id into the response dict.

What is MISSING from those unit tests: an end-to-end HTTP test that exercises
the full MCP JSON-over-HTTP transport layer. A regression in ``mcp.py``'s
``_build_error_response`` (e.g., accidentally removing ``correlation_id`` from
the dict) or a FastMCP serialisation change would be invisible to the existing
unit tests. This file fills that gap.

Spec coverage
-------------
specs/query/query-execution.spec.md:
  - Requirement: Read-Only Enforcement
  - Scenario: Keyword blacklist (secondary)
    "AND the error response includes a correlation ID for log lookup"

Run with:
    make instance-up
    source .instances/$(basename $(pwd))/.env.instance
    cd src/api && uv run pytest tests/integration/test_query_mcp_http.py \\
        -v -m integration

Alternatively, with a local Keycloak:
    cd src/api && uv run pytest tests/integration/test_query_mcp_http.py \\
        -v -m "integration and keycloak"
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from httpx import ASGITransport, AsyncClient

from graph.infrastructure.tenant_graph_handler import AGEGraphProvisioner
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings
from main import app

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client with full app lifespan.

    Starts the Kartograph application (including MCP server lifespan) in-process.
    The lifespan creates the default tenant via TenantBootstrapService, ensuring
    ``default_tenant_id`` can find it in the DB.
    """
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture
async def api_key_secret(
    async_client: AsyncClient,
    tenant_auth_headers: dict[str, str],
) -> str:
    """Create a fresh API key and return the plaintext secret.

    Uses JWT auth to create the key via the IAM API.  The key is scoped
    to the default tenant (from ``tenant_auth_headers``).
    """
    unique_name = f"mcp-http-test-{uuid.uuid4().hex[:8]}"
    response = await async_client.post(
        "/iam/api-keys",
        json={"name": unique_name, "expires_in_days": 1},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 201, f"Failed to create API key: {response.json()}"
    return response.json()["secret"]


@pytest_asyncio.fixture
async def provisioned_tenant_graph(
    async_client: AsyncClient,  # ensures app is started → default tenant created
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
    default_tenant_id: str,
) -> str:
    """Ensure the caller's tenant AGE graph is provisioned.

    ``TenantAwareQueryGraphRepository.execute_cypher()`` checks graph existence
    BEFORE the keyword blacklist.  If the graph is absent, the error type is
    ``"execution_error"`` (graph not found) rather than ``"forbidden"``.

    This fixture provisions the graph so that the blacklist check is reached
    and the correct ``"forbidden"`` response (with ``correlation_id``) is
    produced.

    Args:
        async_client: Dependency that guarantees the app lifespan has run and
            the default tenant exists in the DB.
        integration_db_settings: DB connection settings.
        integration_connection_pool: Shared psycopg2 connection pool.
        default_tenant_id: The default tenant's ULID — used to derive the
            expected graph name (``tenant_{id}``).

    Returns:
        The tenant_id whose graph was provisioned.
    """
    factory = ConnectionFactory(
        integration_db_settings, pool=integration_connection_pool
    )
    provisioner = AGEGraphProvisioner(connection_factory=factory)
    graph_name = f"tenant_{default_tenant_id}"
    provisioner.ensure_graph_exists(graph_name)
    return default_tenant_id


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_asgi_httpx_factory(
    asgi_app,
) -> httpx.AsyncClient:
    """Return an ``McpHttpClientFactory`` that wraps the ASGI app.

    FastMCP's ``StreamableHttpTransport`` accepts an optional
    ``httpx_client_factory`` so we can substitute a real HTTP server with
    an in-process ASGI transport — no network required.

    The factory signature is::

        def factory(
            headers: dict[str, str] | None = None,
            timeout: httpx.Timeout | None = None,
            auth: httpx.Auth | None = None,
        ) -> httpx.AsyncClient: ...
    """

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app),
            base_url="http://test",
            headers=headers or {},
            timeout=timeout,
            auth=auth,
        )

    return factory  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMCPForbiddenQueryHTTPResponse:
    """HTTP-level tests for forbidden query response.

    These tests exercise the full stack:
      API key auth → MCP protocol parsing → query_graph tool →
      MCPQueryService → TenantAwareQueryGraphRepository →
      QueryGraphRepository._validate_read_only → QueryForbiddenError →
      MCPQueryService returns QueryError(error_type='forbidden') →
      _build_error_response serialises correlation_id →
      MCP HTTP response body

    Spec: specs/query/query-execution.spec.md
      Requirement: Read-Only Enforcement
      Scenario: Keyword blacklist (secondary)
    """

    @pytest.mark.asyncio
    async def test_forbidden_query_response_includes_correlation_id(
        self,
        async_client: AsyncClient,
        api_key_secret: str,
        provisioned_tenant_graph: str,
    ) -> None:
        """Forbidden query HTTP response MUST include ``correlation_id``.

        Spec: Keyword blacklist (secondary) —
        "AND the error response includes a correlation ID for log lookup"

        This verifies the end-to-end HTTP transport layer, catching regressions
        that unit tests cannot detect (e.g., accidentally removing
        ``correlation_id`` from ``_build_error_response``, or a FastMCP
        serialisation change that strips the field).
        """
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": api_key_secret},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                {"cypher": "CREATE (n:Test)"},
            )

        # MCP tool call itself must succeed (no protocol-level error)
        assert result.is_error is False, (
            f"Expected a tool result, got an MCP protocol error: {result}"
        )

        # Parse the tool's return dict
        tool_result = result.data

        # 1. success field is False
        assert tool_result["success"] is False, (
            f"Expected success=False, got: {tool_result}"
        )

        # 2. error_type is "forbidden"
        assert tool_result["error_type"] == "forbidden", (
            f"Expected error_type='forbidden', got: {tool_result}"
        )

        # 3. correlation_id key is present
        assert "correlation_id" in tool_result, (
            f"Expected 'correlation_id' key in response, "
            f"got keys: {list(tool_result.keys())}"
        )

        # 4. correlation_id is a non-empty string (UUID format)
        correlation_id = tool_result["correlation_id"]
        assert correlation_id is not None, "correlation_id must not be None"
        assert isinstance(correlation_id, str), (
            f"correlation_id must be a string, got {type(correlation_id)}"
        )
        assert len(correlation_id) > 0, "correlation_id must not be empty"

        # 5. The raw query text does NOT appear in the response body
        #    (spec: "a redacted reference is logged (not the raw query text)")
        response_str = json.dumps(tool_result)
        assert "CREATE (n:Test)" not in response_str, (
            f"Raw query text must not appear in the response (spec: redacted "
            f"reference). Found in: {response_str!r}"
        )

    @pytest.mark.asyncio
    async def test_forbidden_query_error_type_is_forbidden(
        self,
        async_client: AsyncClient,
        api_key_secret: str,
        provisioned_tenant_graph: str,
    ) -> None:
        """Forbidden keyword queries MUST return error_type='forbidden' at HTTP level.

        Spec: Error Categorization — Scenario: Forbidden query
        "GIVEN a query containing mutation keywords
         THEN the error type is 'forbidden'"

        Tests a different forbidden keyword (DELETE) to complement the
        CREATE test above.
        """
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": api_key_secret},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                {"cypher": "MATCH (n) DELETE n"},
            )

        assert result.is_error is False
        tool_result = result.data

        assert tool_result["success"] is False
        assert tool_result["error_type"] == "forbidden"
        # correlation_id must also be present for DELETE-based forbidden errors
        assert "correlation_id" in tool_result
        assert len(str(tool_result["correlation_id"])) > 0
