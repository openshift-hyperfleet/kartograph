"""HTTP-level integration tests for query_graph successful response shape.

Tests the full HTTP stack from the MCP HTTP endpoint through to the AGE graph,
verifying that a successful Cypher query returns the four required fields:
  - rows         — list of result rows
  - row_count    — non-negative integer equal to len(rows)
  - truncated    — boolean
  - execution_time_ms — non-negative number

Why this test exists
--------------------
The *unit* tests verify each layer in isolation via ``FakeMCPQueryService``
(``test_mcp_query_tool_wiring.py``) and assert that all four keys are present.
However, no existing test verifies these fields at the **MCP HTTP transport
layer**.  Specifically:

- ``test_query_mcp_http.py`` exercises the HTTP path but covers only **error
  responses** (forbidden query, timeout).  The success path — where a valid
  Cypher query returns data — is not tested at the HTTP level.
- ``test_query_mcp.py`` tests the service and repository layers directly (not
  via the MCP HTTP protocol).  It does not exercise the MCP framing layer or
  the ``query_graph`` tool's JSON serialisation path.

Without an HTTP-level success test, a regression that breaks the tool's JSON
serialisation (e.g., renaming a key, omitting ``execution_time_ms``, or
failing to set ``success=True``) would not be caught until a real MCP client
attempted a query.

Design notes
------------
- Uses direct DB API key insertion (no Keycloak) with the fake OIDC
  pre-configured test user ID ``ALICE_USER_ID = "alice-test-id"``.
- Fixtures are class-scoped with ``loop_scope="class"`` so the ASGI app
  lifespan (which cannot be restarted) persists across all tests in the class.
- AGE graph provisioning follows the ``test_secure_enclave_mcp.py`` pattern.

Spec coverage
-------------
specs/query/mcp-server.spec.md:
  - Requirement: Graph Query Tool
  - Scenario: Successful query
    "THEN the results are returned with rows, row count, truncation flag,
     and execution time"

Run with:
    make instance-up
    source .instances/$(basename $(pwd))/.env.instance
    cd src/api && uv run pytest \\
        tests/integration/query/test_query_mcp_http_success.py \\
        -v -m integration

Spec-Ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
Task-Ref: task-141
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime, timedelta

import bcrypt
import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.tenant_graph_handler import AGEGraphProvisioner
from iam.application.security import extract_prefix, generate_api_key_secret
from iam.domain.value_objects import APIKeyId
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings
from main import app

pytestmark = [
    pytest.mark.integration,
    # All tests in this module share the class-scoped event loop that backs
    # the class-scoped LifespanManager (async_client fixture).  Without
    # loop_scope="class" the test coroutines run in a function-scoped loop
    # that differs from the loop on which the app's connection pools were
    # created, causing "Future attached to a different loop" errors.
    pytest.mark.asyncio(loop_scope="class"),
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Fake OIDC pre-configured test user ID (from tests/fakes/oidc_provider.py).
#: MCPApiKeyAuthMiddleware resolves user_id from the API key's created_by_user_id.
ALICE_USER_ID = "alice-test-id"

#: Label used for test nodes; unlikely to exist in other test data.
_SUCCESS_TEST_LABEL = "SuccessQueryTestNode141"


# ---------------------------------------------------------------------------
# MCP client helper
# ---------------------------------------------------------------------------


def _make_asgi_httpx_factory(
    asgi_app,
) -> Callable[..., httpx.AsyncClient]:
    """Return an MCP httpx client factory backed by the in-process ASGI app.

    FastMCP's StreamableHttpTransport accepts an optional httpx_client_factory
    so we can substitute a real HTTP server with an in-process ASGI transport.
    No network required.

    The factory signature matches what StreamableHttpTransport expects::

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
# Fixtures: app lifespan
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Start the Kartograph application once per test class.

    Class-scoped so that the StreamableHTTPSessionManager (which cannot be
    restarted after its first ``run()`` call) stays alive across all tests in
    the class.  The lifespan runs TenantBootstrapService, which creates the
    default tenant on first startup.

    ``loop_scope="class"`` ensures all class-scoped fixtures share a single
    event loop, avoiding "event loop is closed" errors between tests.
    """
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# ---------------------------------------------------------------------------
# Fixtures: tenant resolution
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def success_tenant_id(
    async_client: AsyncClient,  # ensures app lifespan has run → default tenant created
    integration_db_settings: DatabaseSettings,
) -> str:
    """Retrieve the default tenant ID created by the app bootstrap.

    Depends on async_client to guarantee the app's startup lifespan has run
    and the default tenant has been written to the database.
    """
    from infrastructure.settings import get_iam_settings

    iam_settings = get_iam_settings()
    engine = create_write_engine(integration_db_settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            text("SELECT id FROM tenants WHERE name = :name"),
            {"name": iam_settings.default_tenant_name},
        )
        row = result.scalar_one_or_none()

    await engine.dispose()

    assert row is not None, (
        f"Default tenant '{iam_settings.default_tenant_name}' not found. "
        "Ensure app lifespan ran (async_client fixture)."
    )
    return str(row)


# ---------------------------------------------------------------------------
# Fixtures: AGE graph provisioning
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def provisioned_success_graph(
    async_client: AsyncClient,
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
    success_tenant_id: str,
) -> AsyncGenerator[AgeGraphClient, None]:
    """Provision the tenant AGE graph and return a connected AgeGraphClient.

    The graph name is ``tenant_{success_tenant_id}``, matching the routing
    used by TenantAwareQueryGraphRepository for the default tenant.

    Pre-cleanup removes any stale test nodes from a previous interrupted run.
    Post-cleanup removes nodes inserted during this test.
    """
    factory = ConnectionFactory(
        integration_db_settings, pool=integration_connection_pool
    )
    graph_name = f"tenant_{success_tenant_id}"

    # Provision the graph (idempotent — no-op if it already exists)
    provisioner = AGEGraphProvisioner(connection_factory=factory)
    provisioner.ensure_graph_exists(graph_name)

    # Connect the client for test data setup
    tenant_client = AgeGraphClient(
        integration_db_settings,
        connection_factory=factory,
        graph_name=graph_name,
    )
    tenant_client.connect()

    # Pre-cleanup: remove stale test nodes from any previous interrupted run
    try:
        tenant_client.execute_cypher(f"MATCH (n:{_SUCCESS_TEST_LABEL}) DETACH DELETE n")
    except Exception:
        pass

    yield tenant_client

    # Post-cleanup: remove nodes inserted during this test
    try:
        tenant_client.execute_cypher(f"MATCH (n:{_SUCCESS_TEST_LABEL}) DETACH DELETE n")
    except Exception:
        pass

    tenant_client.disconnect()


# ---------------------------------------------------------------------------
# Fixtures: API key insertion (direct DB, no Keycloak)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def success_api_key(
    async_client: AsyncClient,  # ensures app started → tenant exists in DB
    integration_db_settings: DatabaseSettings,
    success_tenant_id: str,
) -> AsyncGenerator[str, None]:
    """Insert an API key for alice (user_id='alice-test-id') and return the secret.

    Uses direct DB insertion (no Keycloak dependency) with a low bcrypt work
    factor (4 vs. production 12) for test speed.

    Class-scoped so the same key is reused across all tests in the class; one
    insert/delete per class run.
    """
    secret = generate_api_key_secret()
    key_hash = bcrypt.hashpw(secret.encode(), bcrypt.gensalt(4)).decode()
    prefix = extract_prefix(secret)
    api_key_id = APIKeyId.generate().value
    expires_at = datetime.now(UTC) + timedelta(days=1)

    engine = create_write_engine(integration_db_settings)
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
                "user_id": ALICE_USER_ID,
                "tenant_id": success_tenant_id,
                "name": f"success-test-{api_key_id[:8]}",
                "key_hash": key_hash,
                "prefix": prefix,
                "expires_at": expires_at,
            },
        )
        await session.commit()

    await engine.dispose()

    yield secret

    # Teardown: remove the API key to avoid polluting the api_keys table
    engine = create_write_engine(integration_db_settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM api_keys WHERE id = :id"),
            {"id": api_key_id},
        )
        await session.commit()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestQueryGraphSuccessResponse:
    """HTTP-level tests for query_graph successful response field shape.

    These tests exercise the full stack:
      API key auth → MCP protocol parsing → query_graph tool →
      MCPQueryService → TenantAwareQueryGraphRepository →
      real AGE graph → JSON serialisation → MCP HTTP response body

    A regression in ``mcp.py``'s ``query_graph`` (e.g., accidentally renaming
    ``row_count`` to ``count``, omitting ``execution_time_ms``, or failing to
    set ``success=True``) or a FastMCP serialisation change would be invisible
    to the unit test pyramid.  This class fills that gap with real end-to-end
    HTTP transport exercises.

    Spec: specs/query/mcp-server.spec.md
      Requirement: Graph Query Tool
      Scenario: Successful query
        "GIVEN an authenticated MCP client
         WHEN the client calls query_graph with a valid Cypher query
         THEN the query executes against the caller's tenant graph
         AND the results are returned with rows, row count, truncation flag,
             and execution time"
    """

    async def test_successful_query_response_contains_all_required_fields(
        self,
        async_client: AsyncClient,
        success_api_key: str,
        provisioned_success_graph: AgeGraphClient,
    ) -> None:
        """A query returning rows MUST include all four success response fields.

        Spec: Successful query —
        "AND the results are returned with rows, row count, truncation flag,
         and execution time"

        Steps:
          1. Insert one test node into the tenant AGE graph.
          2. Query it via the MCP HTTP transport.
          3. Assert success=True.
          4. Assert "rows" is present and is a list with exactly 1 entry.
          5. Assert "row_count" equals len(rows) and is non-negative.
          6. Assert "truncated" is a boolean.
          7. Assert "execution_time_ms" is a non-negative number.
        """
        # Insert one node for the query to find
        provisioned_success_graph.execute_cypher(
            f"CREATE (n:{_SUCCESS_TEST_LABEL} {{name: 'query-success-test'}})"
        )

        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": success_api_key},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                {"cypher": f"MATCH (n:{_SUCCESS_TEST_LABEL}) RETURN n LIMIT 1"},
            )

        # MCP tool call must succeed at the protocol level
        assert result.is_error is False, (
            f"Expected a tool result, got an MCP protocol error: {result}"
        )

        tool_result = result.data

        # 1. success must be True
        assert tool_result["success"] is True, (
            f"Expected success=True for a valid MATCH query, got: {tool_result}"
        )

        # 2. "rows" must be present and be a list
        assert "rows" in tool_result, (
            f"Expected 'rows' key in success response, got keys: {list(tool_result.keys())}"
        )
        rows = tool_result["rows"]
        assert isinstance(rows, list), (
            f"'rows' must be a list, got {type(rows).__name__}"
        )

        # 3. "row_count" must be present, non-negative, and equal len(rows)
        assert "row_count" in tool_result, (
            f"Expected 'row_count' key in success response, got keys: {list(tool_result.keys())}"
        )
        row_count = tool_result["row_count"]
        assert isinstance(row_count, int), (
            f"'row_count' must be an int, got {type(row_count).__name__}"
        )
        assert row_count >= 0, f"'row_count' must be non-negative, got {row_count}"
        assert row_count == len(rows), (
            f"'row_count' ({row_count}) must equal len(rows) ({len(rows)})"
        )

        # The inserted node must appear in the result
        assert row_count >= 1, (
            f"Expected at least 1 row after inserting a {_SUCCESS_TEST_LABEL} node, "
            f"got row_count={row_count}"
        )

        # 4. "truncated" must be present and be a boolean
        assert "truncated" in tool_result, (
            f"Expected 'truncated' key in success response, got keys: {list(tool_result.keys())}"
        )
        assert isinstance(tool_result["truncated"], bool), (
            f"'truncated' must be a bool, got {type(tool_result['truncated']).__name__}"
        )

        # 5. "execution_time_ms" must be present and be non-negative
        assert "execution_time_ms" in tool_result, (
            f"Expected 'execution_time_ms' key in success response, "
            f"got keys: {list(tool_result.keys())}"
        )
        execution_time_ms = tool_result["execution_time_ms"]
        assert isinstance(execution_time_ms, (int, float)), (
            f"'execution_time_ms' must be a number, got {type(execution_time_ms).__name__}"
        )
        assert execution_time_ms >= 0, (
            f"'execution_time_ms' must be non-negative, got {execution_time_ms}"
        )

    async def test_successful_empty_query_response_shape(
        self,
        async_client: AsyncClient,
        success_api_key: str,
        provisioned_success_graph: AgeGraphClient,
    ) -> None:
        """A query matching zero rows returns an empty success response.

        Spec: Successful query —
        "AND the results are returned with rows, row count, truncation flag,
         and execution time"

        Queries for a label that is guaranteed not to exist in the test graph.
        This verifies the empty-result path produces the same four fields with
        sensible defaults (rows=[], row_count=0, truncated=False).

        Steps:
          1. Query for a label that does not exist in the tenant graph.
          2. Assert success=True.
          3. Assert rows == [].
          4. Assert row_count == 0.
          5. Assert truncated is False.
          6. Assert "execution_time_ms" is present and non-negative.
        """
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": success_api_key},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                # Label is unique enough that it will never exist in any test graph
                {"cypher": "MATCH (n:AbsolutelyNoSuchLabelTask141) RETURN n"},
            )

        # MCP tool call must succeed at the protocol level
        assert result.is_error is False, (
            f"Expected a tool result, got an MCP protocol error: {result}"
        )

        tool_result = result.data

        # 1. success must be True (empty result is not an error)
        assert tool_result["success"] is True, (
            f"Expected success=True for an empty-result MATCH query, got: {tool_result}"
        )

        # 2. rows must be an empty list
        assert "rows" in tool_result, (
            f"Expected 'rows' key in empty-result response, got keys: {list(tool_result.keys())}"
        )
        assert tool_result["rows"] == [], (
            f"Expected rows=[] for a no-match query, got: {tool_result['rows']}"
        )

        # 3. row_count must be 0
        assert "row_count" in tool_result, (
            f"Expected 'row_count' key in empty-result response, got keys: {list(tool_result.keys())}"
        )
        assert tool_result["row_count"] == 0, (
            f"Expected row_count=0, got: {tool_result['row_count']}"
        )

        # 4. truncated must be False (no rows to truncate)
        assert "truncated" in tool_result, (
            f"Expected 'truncated' key in empty-result response, got keys: {list(tool_result.keys())}"
        )
        assert tool_result["truncated"] is False, (
            f"Expected truncated=False for empty result, got: {tool_result['truncated']}"
        )

        # 5. execution_time_ms must be present and non-negative
        assert "execution_time_ms" in tool_result, (
            f"Expected 'execution_time_ms' key in empty-result response, "
            f"got keys: {list(tool_result.keys())}"
        )
        execution_time_ms = tool_result["execution_time_ms"]
        assert isinstance(execution_time_ms, (int, float)), (
            f"'execution_time_ms' must be a number, got {type(execution_time_ms).__name__}"
        )
        assert execution_time_ms >= 0, (
            f"'execution_time_ms' must be non-negative, got {execution_time_ms}"
        )
