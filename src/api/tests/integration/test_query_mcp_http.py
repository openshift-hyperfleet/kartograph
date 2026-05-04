"""HTTP-level integration tests for MCP query error response contracts.

Tests the full HTTP stack from the MCP HTTP endpoint through to the Cypher
execution safeguards, verifying that:
  - Forbidden query responses include the ``correlation_id`` field.
  - Timeout query responses include ``error_type="timeout"`` and ``correlation_id``.
  - Tenant graph not found responses include ``error_type="execution_error"``.

Why this test exists
--------------------
The *unit* tests verify each layer in isolation:
- ``test_query_repository.py::test_forbidden_error_has_correlation_id`` — repository
  assigns a correlation_id to QueryForbiddenError.
- ``test_application_services.py::test_forbidden_error_includes_correlation_id_in_response``
  — MCPQueryService preserves correlation_id in the returned QueryError.
- ``test_mcp_query_tool.py::TestBuildErrorResponseForbiddenErrors`` — _build_error_response
  serialises correlation_id into the response dict.
- ``test_query_repository.py::test_timeout_raises_query_timeout_error`` — repository
  raises QueryTimeoutError when PostgreSQL cancels the statement.
- ``test_application_services.py::TestExecuteCypherQuery::test_categorizes_timeout_error``
  — MCPQueryService converts QueryTimeoutError → QueryError(error_type="timeout").
- ``test_mcp_query_tool.py::TestBuildErrorResponseTimeoutErrors`` — _build_error_response
  serialises correlation_id for timeout errors.
- ``test_tenant_routing.py::TestTenantAwareQueryGraphRepository`` — unit tests for
  graph-not-found rejection before the database is reached.

What is MISSING from those unit tests: an end-to-end HTTP test that exercises
the full MCP JSON-over-HTTP transport layer. A regression in ``mcp.py``'s
``_build_error_response`` (e.g., accidentally removing ``correlation_id`` from
the dict, or dropping the timeout branch) or a FastMCP serialisation change
would be invisible to the existing unit tests. This file fills that gap.

Spec coverage
-------------
specs/query/query-execution.spec.md:
  - Requirement: Read-Only Enforcement
  - Scenario: Keyword blacklist (secondary)
    "AND the error response includes a correlation ID for log lookup"
  - Requirement: Per-Tenant Graph Routing
  - Scenario: Tenant graph not found
    "GIVEN a tenant whose AGE graph has not been provisioned
     WHEN a query is submitted
     THEN the request is rejected with an execution error before reaching the database"

specs/query/mcp-server.spec.md:
  - Requirement: Graph Query Tool
  - Scenario: Query timeout
    "GIVEN a query that exceeds the timeout
     WHEN the query is executed
     THEN it is terminated and returned with error type 'timeout'"

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
from collections.abc import AsyncGenerator, Callable

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from httpx import ASGITransport, AsyncClient

from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.tenant_graph_handler import AGEGraphProvisioner
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings
from main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Cypher query that reliably exceeds a 1-second PostgreSQL statement_timeout.
#
# A 4-way Cartesian product over TimeoutNode entities (150 nodes = 150^4 =
# 506,250,000 combos).  CI hardware evaluates ~18M combinations/second, so
# this produces ~28 seconds of work — well beyond the 1-second timeout even
# on 10x faster hardware.  A 3-way product (3.375M combos) completes in
# ~188ms on CI runners and does NOT reliably trigger the timeout.
#
# RETURN count(*) forces full evaluation — no short-circuit via LIMIT applies.
_TIMEOUT_SLOW_QUERY = (
    "MATCH (a:TimeoutNode), (b:TimeoutNode), (c:TimeoutNode), (d:TimeoutNode)"
    " RETURN count(*)"
)

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
) -> Callable[..., httpx.AsyncClient]:
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
        follow_redirects: bool = True,
        **kwargs,
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app),
            base_url="http://test",
            headers=headers or {},
            timeout=timeout,
            auth=auth,
            follow_redirects=follow_redirects,
        )

    return factory


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


# ---------------------------------------------------------------------------
# Timeout fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def provisioned_tenant_graph_with_timeout_data(
    async_client: AsyncClient,  # ensures app lifespan ran → default tenant created
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
    default_tenant_id: str,
) -> AsyncGenerator[str, None]:
    """Provision the tenant AGE graph with 150 TimeoutNode entities.

    Creates the tenant graph (if absent) and populates it with 150 labeled
    nodes so that the 4-way Cartesian product query::

        MATCH (a:TimeoutNode), (b:TimeoutNode), (c:TimeoutNode), (d:TimeoutNode)
        RETURN count(*)

    generates 506,250,000 (150^4) combinations, reliably exceeding a 1-second
    PostgreSQL statement_timeout on any hardware. A 3-way product (150^3 =
    3.375M combos) completes in ~188ms on CI runners and is not reliable.

    The 150 nodes are created via individual ``CREATE`` calls using the raw
    ``AgeGraphClient`` (no read-only restriction), each committed in its own
    transaction.  The load is intentionally modest so the fixture completes
    in well under the test suite's patience threshold.

    Cleans up TimeoutNode entities before setup (guards against leftover nodes
    from a prior test run that failed before teardown) and after yield so that
    the next test always starts with exactly 150 nodes.

    Args:
        async_client: Dependency ensuring the app lifespan has run and the
            default tenant exists in the DB before graph provisioning.
        integration_db_settings: DB connection settings.
        integration_connection_pool: Shared psycopg2 connection pool.
        default_tenant_id: The default tenant's ULID, used to derive the
            tenant graph name (``tenant_{id}``).

    Yields:
        The tenant_id whose graph was provisioned and populated.
    """
    factory = ConnectionFactory(
        integration_db_settings, pool=integration_connection_pool
    )
    provisioner = AGEGraphProvisioner(connection_factory=factory)
    graph_name = f"tenant_{default_tenant_id}"
    provisioner.ensure_graph_exists(graph_name)

    client = AgeGraphClient(
        settings=integration_db_settings,
        connection_factory=factory,
        graph_name=graph_name,
        auto_create=False,
    )

    # Pre-test cleanup: remove any TimeoutNode entities left by a prior run.
    client.connect()
    try:
        client.execute_cypher("MATCH (n:TimeoutNode) DELETE n")
    finally:
        client.disconnect()

    # Populate the graph with 150 TimeoutNode entities.
    # Using AgeGraphClient directly (bypasses the read-only QueryGraphRepository).
    client.connect()
    try:
        for i in range(150):
            client.execute_cypher(f"CREATE (n:TimeoutNode {{idx: {i}}})")
    finally:
        client.disconnect()

    yield default_tenant_id

    # Teardown: remove TimeoutNode entities so the next test starts clean.
    client.connect()
    try:
        client.execute_cypher("MATCH (n:TimeoutNode) DELETE n")
    finally:
        client.disconnect()


# ---------------------------------------------------------------------------
# Tests — timeout query response
# ---------------------------------------------------------------------------


class TestMCPTimeoutQueryHTTPResponse:
    """HTTP-level tests for timeout query response contract.

    These tests exercise the full stack:
      API key auth → MCP protocol parsing → query_graph tool →
      MCPQueryService → TenantAwareQueryGraphRepository →
      QueryGraphRepository.execute_cypher → PostgreSQL statement_timeout →
      QueryTimeoutError → MCPQueryService returns QueryError(error_type='timeout') →
      _build_error_response serialises correlation_id →
      MCP HTTP response body

    A regression in ``mcp.py``'s ``_build_error_response`` (e.g., accidentally
    dropping ``correlation_id`` from the timeout branch) or a FastMCP
    serialisation change would be invisible to the unit test pyramid. This
    class fills that gap with a real end-to-end HTTP transport exercise.

    Spec: specs/query/mcp-server.spec.md
      Requirement: Graph Query Tool
      Scenario: Query timeout

    Spec: specs/query/query-execution.spec.md
      Requirement: Timeout Enforcement — Scenario: Query exceeds timeout
      Requirement: Error Categorization — Scenario: Timeout error
    """

    @pytest.mark.asyncio
    async def test_timeout_query_error_type_is_timeout(
        self,
        async_client: AsyncClient,
        api_key_secret: str,
        provisioned_tenant_graph_with_timeout_data: str,
    ) -> None:
        """Timeout query HTTP response MUST return error_type='timeout'.

        Spec: Graph Query Tool — Scenario: Query timeout —
        "GIVEN a query that exceeds the timeout (default 30 seconds, max 60 seconds)
         WHEN the query is executed
         THEN it is terminated and returned with error type 'timeout'"

        Sends a 3-way Cartesian product Cypher query over 150 TimeoutNode
        entities (3,375,000 combinations) with ``timeout_seconds=1`` via the
        MCP HTTP transport.  The PostgreSQL ``statement_timeout`` fires before
        the query completes, causing ``QueryGraphRepository`` to raise
        ``QueryTimeoutError``, which ``MCPQueryService`` converts to a
        ``QueryError(error_type="timeout")``.  The MCP tool returns a response
        dict with ``success=False`` and ``error_type="timeout"``.
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
                {
                    "cypher": _TIMEOUT_SLOW_QUERY,
                    "timeout_seconds": 1,
                },
            )

        # MCP tool call itself must succeed at the protocol level (no MCP error)
        assert result.is_error is False, (
            f"Expected a tool result, got an MCP protocol error: {result}"
        )

        tool_result = result.data

        # 1. success must be False (query did not complete successfully)
        assert tool_result["success"] is False, (
            f"Expected success=False for timeout query, got: {tool_result}"
        )

        # 2. error_type must be "timeout" (not "execution_error" or "forbidden")
        assert tool_result["error_type"] == "timeout", (
            f"Expected error_type='timeout', got: {tool_result}"
        )

    @pytest.mark.asyncio
    async def test_timeout_query_response_includes_correlation_id(
        self,
        async_client: AsyncClient,
        api_key_secret: str,
        provisioned_tenant_graph_with_timeout_data: str,
    ) -> None:
        """Timeout query HTTP response MUST include a non-empty correlation_id.

        Spec: Timeout Enforcement — Scenario: Query exceeds timeout —
        "THEN a timeout error is returned with a correlation ID for debugging"

        Spec: Error Categorization — Scenario: Timeout error —
        "GIVEN a query that exceeds the timeout
         THEN the error type is 'timeout'"

        The ``correlation_id`` links the error response to the server-side log
        entry so support staff can retrieve the redacted log context without the
        raw query text being exposed in the API response.  A regression that
        drops ``correlation_id`` from ``_build_error_response``'s timeout branch
        would break this contract.
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
                {
                    "cypher": _TIMEOUT_SLOW_QUERY,
                    "timeout_seconds": 1,
                },
            )

        assert result.is_error is False, (
            f"Expected a tool result, got an MCP protocol error: {result}"
        )

        tool_result = result.data

        # correlation_id key must be present in the response
        assert "correlation_id" in tool_result, (
            f"Expected 'correlation_id' key in timeout response, "
            f"got keys: {list(tool_result.keys())}"
        )

        # correlation_id must be a non-empty string (UUID format)
        correlation_id = tool_result["correlation_id"]
        assert correlation_id is not None, "correlation_id must not be None"
        assert isinstance(correlation_id, str), (
            f"correlation_id must be a string, got {type(correlation_id)}"
        )
        assert len(correlation_id) > 0, "correlation_id must not be empty"


# ---------------------------------------------------------------------------
# Tests — tenant graph not found response
# ---------------------------------------------------------------------------


class TestMCPTenantGraphNotFoundHTTPResponse:
    """HTTP-level tests for the tenant-graph-not-found error response.

    These tests exercise the full stack WITHOUT provisioning the AGE graph,
    exercising the guard in TenantAwareQueryGraphRepository that rejects
    queries before they reach the database when the tenant graph is absent.

    Stack exercised:
      API key auth → MCP protocol parsing → query_graph tool →
      MCPQueryService → TenantAwareQueryGraphRepository →
      graph existence check fails → QueryExecutionError →
      MCPQueryService returns QueryError(error_type='execution_error') →
      _build_error_response → MCP HTTP response body

    The unit tests in ``test_tenant_routing.py`` verify the routing layer in
    isolation; this class confirms the behaviour is preserved end-to-end over
    the MCP HTTP transport — a layer invisible to the unit pyramid.

    Spec: specs/query/query-execution.spec.md
      Requirement: Per-Tenant Graph Routing
      Scenario: Tenant graph not found
    """

    @pytest.mark.asyncio
    async def test_query_without_provisioned_graph_returns_execution_error(
        self,
        async_client: AsyncClient,
        api_key_secret: str,
    ) -> None:
        """Querying without a provisioned tenant AGE graph yields execution_error.

        Spec: Per-Tenant Graph Routing — Scenario: Tenant graph not found —
        "GIVEN a tenant whose AGE graph has not been provisioned
         WHEN a query is submitted
         THEN the request is rejected with an execution error before reaching
         the database"

        The ``provisioned_tenant_graph`` fixture is intentionally absent so that
        the AGE graph for the default tenant does NOT exist.  The
        ``TenantAwareQueryGraphRepository`` must detect the absence and raise
        ``QueryExecutionError`` before the query reaches PostgreSQL.

        ``MCPQueryService`` converts ``QueryExecutionError`` to a
        ``QueryError(error_type="execution_error")``, which
        ``_build_error_response`` serialises into the MCP tool response.
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
                {"cypher": "MATCH (n) RETURN n LIMIT 1"},
            )

        # MCP tool call itself must succeed at the protocol level (no MCP error)
        assert result.is_error is False, (
            f"Expected a tool result, got an MCP protocol error: {result}"
        )

        tool_result = result.data

        # 1. success must be False (query was rejected before reaching DB)
        assert tool_result["success"] is False, (
            f"Expected success=False when tenant graph is not provisioned, "
            f"got: {tool_result}"
        )

        # 2. error_type must be "execution_error" (graph not found ≠ forbidden)
        assert tool_result["error_type"] == "execution_error", (
            f"Expected error_type='execution_error', got: {tool_result}"
        )

        # 3. message must reference graph/tenant absence for debuggability
        message = tool_result.get("message", "")
        message_lower = message.lower()
        assert any(
            keyword in message_lower
            for keyword in (
                "does not exist",
                "not found",
                "graph",
                "provision",
                "tenant",
            )
        ), f"Expected message to reference graph absence, got: {message!r}"

    @pytest.mark.asyncio
    async def test_query_without_provisioned_graph_error_occurs_before_database(
        self,
        async_client: AsyncClient,
        api_key_secret: str,
    ) -> None:
        """Graph-existence check runs before keyword validation (spec: before DB).

        Spec: Per-Tenant Graph Routing — Scenario: Tenant graph not found —
        "THEN the request is rejected with an execution error before reaching
        the database"

        This test submits a write query that would ordinarily be caught by the
        keyword blacklist (READ-ONLY enforcement) if the tenant graph existed.
        Because the graph is absent, the graph-existence guard must fire FIRST,
        returning ``error_type="execution_error"`` rather than
        ``error_type="forbidden"``.

        If the order were reversed and the blacklist ran first, this test would
        receive ``error_type="forbidden"`` — which would be a spec violation.
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
                # CREATE is a blacklisted keyword — would normally yield "forbidden".
                # Since the graph is not provisioned, the existence check must
                # fire first and yield "execution_error" instead.
                {"cypher": "CREATE (n:Test)"},
            )

        # MCP tool call itself must succeed at the protocol level
        assert result.is_error is False, (
            f"Expected a tool result, got an MCP protocol error: {result}"
        )

        tool_result = result.data

        assert tool_result["success"] is False, (
            f"Expected success=False, got: {tool_result}"
        )

        # The graph-existence guard must win over the keyword blacklist.
        # "execution_error" confirms the ordering is correct.
        assert tool_result["error_type"] == "execution_error", (
            f"Expected error_type='execution_error' (graph-not-found guard fires "
            f"before keyword blacklist), got error_type={tool_result.get('error_type')!r}. "
            f"Full response: {tool_result}"
        )
