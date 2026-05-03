"""Integration tests for per-tenant graph routing in the Querying bounded context.

Spec: specs/query/query-execution.spec.md
Requirement: Per-Tenant Graph Routing

Scenarios covered:
  1. Query routed to tenant graph (cross-tenant isolation) — each tenant's
     QueryGraphRepository sees only its own AGE graph; data in one tenant's
     graph is invisible to another tenant's repository.

  2. Tenant graph not found raises QueryExecutionError before DB — when a
     tenant's AGE graph has not been provisioned, the system raises
     QueryExecutionError from TenantAwareQueryGraphRepository (backed by
     AGEGraphExistenceChecker querying ag_catalog.ag_graph) without issuing
     any Cypher to the database.

This file contains two layers of coverage:

Infrastructure-layer (TestPerTenantGraphRouting):
  Direct tests of QueryGraphRepository and TenantAwareQueryGraphRepository
  against a real PostgreSQL/AGE instance.  These exercise the per-tenant
  isolation contract at the repository level.

HTTP-layer (TestPerTenantGraphRoutingHTTP):
  End-to-end tests exercising the full call chain:
    API key auth middleware → get_mcp_query_service() dependency →
    TenantAwareQueryGraphRepository → real PostgreSQL/AGE.

  A regression in the dependency injection (e.g. get_mcp_query_service() not
  propagating tenant_id from the auth context) or in the MCP response
  serialisation (e.g. _build_error_response dropping error_type) would be
  invisible to the infrastructure-layer tests alone.  The HTTP-layer tests
  catch those regressions.

Run with:
    pytest -m integration tests/integration/query/test_tenant_routing.py
    # or via make:
    make instance-up
    source .instances/$(basename $(pwd))/.env.instance
    cd src/api && uv run pytest tests/integration/query/test_tenant_routing.py -v -m integration

Requires: Running PostgreSQL with AGE extension.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Callable, Generator

import bcrypt
import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.tenant_graph_handler import AGEGraphProvisioner
from iam.application.security import extract_prefix, generate_api_key_secret
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings
from main import app
from query.domain.value_objects import QueryExecutionError
from query.infrastructure.query_repository import QueryGraphRepository
from query.infrastructure.tenant_routing import (
    AGEGraphExistenceChecker,
    TenantAwareQueryGraphRepository,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant_graph_name(unique_suffix: str) -> str:
    """Build a deterministic tenant graph name for tests."""
    return f"tenant_{unique_suffix}"


def _drop_graph_if_exists(
    pool: ConnectionPool,
    graph_name: str,
) -> None:
    """Drop an AGE graph, ignoring if it has already been removed."""
    conn = pool.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
                (graph_name,),
            )
            if cursor.fetchone() is not None:
                cursor.execute(
                    "SELECT ag_catalog.drop_graph(%s, true)",
                    (graph_name,),
                )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        pool.return_connection(conn)


def _create_connected_tenant_client(
    settings: DatabaseSettings,
    pool: ConnectionPool,
    graph_name: str,
) -> AgeGraphClient:
    """Create and connect an AgeGraphClient targeting a specific tenant graph.

    Uses auto_create=True so the AGE graph is provisioned if absent.
    """
    factory = ConnectionFactory(settings, pool=pool)
    client = AgeGraphClient(
        settings,
        connection_factory=factory,
        graph_name=graph_name,
        auto_create=True,
    )
    client.connect()
    return client


def _make_asgi_httpx_factory(
    asgi_app,
) -> Callable[..., httpx.AsyncClient]:
    """Return an httpx client factory that wraps the ASGI app.

    FastMCP's StreamableHttpTransport accepts an optional
    ``httpx_client_factory`` so we can substitute a real HTTP server with
    an in-process ASGI transport — no network required.
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

    return factory


# ---------------------------------------------------------------------------
# Infrastructure-layer fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_a_client(
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
) -> Generator[AgeGraphClient, None, None]:
    """Provision tenant A's AGE graph and yield a connected client.

    Drops the graph during teardown to keep the database clean.
    """
    graph_name = _make_tenant_graph_name(f"a_{uuid.uuid4().hex[:8]}")
    client = _create_connected_tenant_client(
        integration_db_settings,
        integration_connection_pool,
        graph_name,
    )
    yield client
    client.disconnect()
    _drop_graph_if_exists(integration_connection_pool, graph_name)


@pytest.fixture
def tenant_b_client(
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
) -> Generator[AgeGraphClient, None, None]:
    """Provision tenant B's AGE graph and yield a connected client.

    Drops the graph during teardown to keep the database clean.
    """
    graph_name = _make_tenant_graph_name(f"b_{uuid.uuid4().hex[:8]}")
    client = _create_connected_tenant_client(
        integration_db_settings,
        integration_connection_pool,
        graph_name,
    )
    yield client
    client.disconnect()
    _drop_graph_if_exists(integration_connection_pool, graph_name)


# ---------------------------------------------------------------------------
# HTTP-layer fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def http_db_session(
    integration_db_settings: DatabaseSettings,
) -> AsyncGenerator[AsyncSession, None]:
    """Async SQLAlchemy session for HTTP-layer test setup (tenant/key creation).

    Function-scoped so each test gets an independent session and teardown
    runs within the same session context.
    """
    engine = create_write_engine(integration_db_settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def async_http_client() -> AsyncGenerator[AsyncClient, None]:
    """ASGI HTTP client wrapping the full Kartograph application.

    Starts the app lifespan (DB connections, outbox worker, MCP server)
    in-process using LifespanManager so the full DI graph is wired.
    No Keycloak dependency — API key auth is purely DB-based.
    """
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture
async def tenant_a_id(
    http_db_session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Create an isolated test tenant A in the DB, clean up after the test.

    Returns a unique tenant ID (ULID-style hex string).
    """
    tenant_id = f"test-ta-{uuid.uuid4().hex[:12]}"
    tenant_name = f"routing-test-tenant-a-{tenant_id}"

    await http_db_session.execute(
        text(
            "INSERT INTO tenants (id, name, created_at, updated_at) "
            "VALUES (:id, :name, NOW(), NOW())"
        ),
        {"id": tenant_id, "name": tenant_name},
    )
    await http_db_session.commit()

    yield tenant_id

    # Teardown: remove dependent rows first, then the tenant
    try:
        await http_db_session.execute(
            text("DELETE FROM api_keys WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        await http_db_session.execute(
            text("DELETE FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        )
        await http_db_session.commit()
    except Exception:
        await http_db_session.rollback()


@pytest_asyncio.fixture
async def tenant_b_id(
    http_db_session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Create an isolated test tenant B in the DB, clean up after the test.

    Returns a unique tenant ID.
    """
    tenant_id = f"test-tb-{uuid.uuid4().hex[:12]}"
    tenant_name = f"routing-test-tenant-b-{tenant_id}"

    await http_db_session.execute(
        text(
            "INSERT INTO tenants (id, name, created_at, updated_at) "
            "VALUES (:id, :name, NOW(), NOW())"
        ),
        {"id": tenant_id, "name": tenant_name},
    )
    await http_db_session.commit()

    yield tenant_id

    try:
        await http_db_session.execute(
            text("DELETE FROM api_keys WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        await http_db_session.execute(
            text("DELETE FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        )
        await http_db_session.commit()
    except Exception:
        await http_db_session.rollback()


@pytest_asyncio.fixture
async def unprovisionied_tenant_id(
    http_db_session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Create a tenant in the DB whose AGE graph is NOT provisioned.

    Used to verify the "tenant graph not found" error path through the
    full HTTP stack.
    """
    tenant_id = f"test-ghost-{uuid.uuid4().hex[:12]}"
    tenant_name = f"routing-test-ghost-tenant-{tenant_id}"

    await http_db_session.execute(
        text(
            "INSERT INTO tenants (id, name, created_at, updated_at) "
            "VALUES (:id, :name, NOW(), NOW())"
        ),
        {"id": tenant_id, "name": tenant_name},
    )
    await http_db_session.commit()

    yield tenant_id

    try:
        await http_db_session.execute(
            text("DELETE FROM api_keys WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        await http_db_session.execute(
            text("DELETE FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        )
        await http_db_session.commit()
    except Exception:
        await http_db_session.rollback()


async def _create_api_key_in_db(
    session: AsyncSession,
    tenant_id: str,
    key_name: str,
) -> str:
    """Insert a valid API key directly into the database and return the plaintext secret.

    Uses bcrypt work factor 4 (vs. production 12) for test speed — the
    validate_mcp_api_key path calls bcrypt.checkpw which respects the cost
    stored in the hash, so this is safe without changing production code.

    Args:
        session: SQLAlchemy async session (must be committed by caller after use).
        tenant_id: The tenant the key is scoped to.
        key_name: A human-readable name for the key row.

    Returns:
        Plaintext API key secret (``karto_...``).
    """
    secret = generate_api_key_secret()
    # Low work factor for speed in tests — does not affect security model
    key_hash = bcrypt.hashpw(secret.encode(), bcrypt.gensalt(4)).decode()
    prefix = extract_prefix(secret)
    api_key_id = f"test-key-{uuid.uuid4().hex[:12]}"
    expires_at = datetime.now(UTC) + timedelta(days=1)

    await session.execute(
        text(
            "INSERT INTO api_keys "
            "(id, created_by_user_id, tenant_id, name, "
            " key_hash, prefix, expires_at, is_revoked, created_at, updated_at) "
            "VALUES "
            "(:id, :user_id, :tenant_id, :name, "
            " :key_hash, :prefix, :expires_at, false, NOW(), NOW())"
        ),
        {
            "id": api_key_id,
            "user_id": f"test-user-{uuid.uuid4().hex[:8]}",
            "tenant_id": tenant_id,
            "name": key_name,
            "key_hash": key_hash,
            "prefix": prefix,
            "expires_at": expires_at.isoformat(),
        },
    )
    await session.commit()
    return secret


def _provision_age_graph_and_seed(
    settings: DatabaseSettings,
    pool: ConnectionPool,
    graph_name: str,
    seed_cypher: str | None = None,
) -> None:
    """Provision an AGE graph and optionally seed it with data.

    Uses AGEGraphProvisioner for idempotent graph creation, then runs
    the seed Cypher via a fresh AgeGraphClient (connected, then disconnected).

    Args:
        settings: Database settings for the connection factory.
        pool: Connection pool to use.
        graph_name: Name of the AGE graph (e.g., ``tenant_{tenant_id}``).
        seed_cypher: Optional Cypher query to run after graph creation.
    """
    factory = ConnectionFactory(settings, pool=pool)
    provisioner = AGEGraphProvisioner(connection_factory=factory)
    provisioner.ensure_graph_exists(graph_name)

    if seed_cypher:
        client = AgeGraphClient(
            settings,
            connection_factory=factory,
            graph_name=graph_name,
        )
        client.connect()
        try:
            client.execute_cypher(seed_cypher)
        finally:
            client.disconnect()


# ---------------------------------------------------------------------------
# Infrastructure-layer tests
# ---------------------------------------------------------------------------


class TestPerTenantGraphRouting:
    """Integration tests for the Per-Tenant Graph Routing requirement.

    These tests exercise the infrastructure layer directly (repository →
    database), providing fast, low-level coverage of the isolation contract.
    For full-stack coverage including auth middleware and FastAPI DI, see
    TestPerTenantGraphRoutingHTTP.

    Spec: specs/query/query-execution.spec.md — Requirement: Per-Tenant Graph Routing
    """

    def test_query_executes_in_tenant_graph(
        self,
        tenant_a_client: AgeGraphClient,
        tenant_b_client: AgeGraphClient,
    ) -> None:
        """
        Spec Scenario: Query routed to tenant graph

        GIVEN two provisioned tenant graphs each belonging to a different tenant
        WHEN data is written only to tenant A's graph
        AND each tenant's QueryGraphRepository executes the same Cypher query
        THEN tenant A's repository returns its own data
        AND tenant B's repository returns nothing (empty graph)
        AND queries never cross tenant boundaries regardless of query content.

        The per-tenant isolation is enforced by the AGE ``cypher('graph_name', …)``
        call: each QueryGraphRepository uses the client's ``graph_name`` so rows
        can never leak across tenant boundaries.
        """
        # Seed tenant A's graph with a distinguishable node.
        tenant_a_client.execute_cypher("CREATE (n:Person {name: 'Alice', tenant: 'A'})")

        # Construct one repository per tenant — each targets its own graph.
        repo_a = QueryGraphRepository(client=tenant_a_client)
        repo_b = QueryGraphRepository(client=tenant_b_client)

        # --- Tenant A query ---
        results_a = repo_a.execute_cypher(
            "MATCH (n:Person) RETURN {name: n.name, tenant: n.tenant}"
        )

        assert len(results_a) == 1, (
            f"Expected exactly 1 Person in tenant A graph '{tenant_a_client.graph_name}', "
            f"got {len(results_a)}"
        )
        assert results_a[0]["name"] == "Alice"
        assert results_a[0]["tenant"] == "A"

        # --- Tenant B query (cross-tenant isolation) ---
        # Tenant B's graph is empty — Alice must NOT appear here.
        results_b = repo_b.execute_cypher(
            "MATCH (n:Person) RETURN {name: n.name, tenant: n.tenant}"
        )

        assert len(results_b) == 0, (
            f"Cross-tenant isolation violated: tenant B's graph "
            f"'{tenant_b_client.graph_name}' returned {len(results_b)} row(s) "
            "that should only exist in tenant A's graph. "
            f"Rows: {results_b}"
        )

    def test_tenant_graph_not_found_raises_before_db(
        self,
        integration_db_settings: DatabaseSettings,
        integration_connection_pool: ConnectionPool,
        graph_client: AgeGraphClient,
    ) -> None:
        """
        Spec Scenario: Tenant graph not found

        GIVEN a tenant whose AGE graph has NOT been provisioned
        WHEN a query is submitted via TenantAwareQueryGraphRepository
        THEN QueryExecutionError is raised before any Cypher reaches the database.
        AND the error message identifies the missing graph by name.

        Implementation details verified:
        - AGEGraphExistenceChecker queries ag_catalog.ag_graph (real DB round-trip)
          and correctly returns False for a graph that does not exist.
        - TenantAwareQueryGraphRepository raises QueryExecutionError immediately,
          never delegating to the inner QueryGraphRepository.

        The inner repository (``graph_client`` / QueryGraphRepository targeting the
        shared test_graph) would succeed if called, so if the outer layer
        incorrectly delegates, the query would return results instead of raising —
        making the test self-verifying.
        """
        # Use a random suffix to guarantee the graph has never been provisioned.
        ghost_tenant_id = f"ghost_{uuid.uuid4().hex[:8]}"
        expected_graph_name = _make_tenant_graph_name(ghost_tenant_id)

        # Production components wired to the real database:
        factory = ConnectionFactory(
            integration_db_settings, pool=integration_connection_pool
        )
        existence_checker = AGEGraphExistenceChecker(factory)

        # Inner repository: the existing graph_client targets test_graph (which
        # DOES exist). If TenantAwareQueryGraphRepository incorrectly skips the
        # existence check and calls the inner repo, the query would succeed and
        # no exception would be raised — failing the assertion below.
        inner_repo = QueryGraphRepository(client=graph_client)

        tenant_repo = TenantAwareQueryGraphRepository(
            tenant_id=ghost_tenant_id,
            inner_repository=inner_repo,
            existence_check_fn=existence_checker,
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            tenant_repo.execute_cypher("MATCH (n) RETURN n")

        error_message = str(exc_info.value)
        assert expected_graph_name in error_message, (
            f"Expected QueryExecutionError message to name the missing graph "
            f"'{expected_graph_name}', but got: {error_message!r}"
        )


# ---------------------------------------------------------------------------
# HTTP-layer tests
# ---------------------------------------------------------------------------


class TestPerTenantGraphRoutingHTTP:
    """HTTP-level integration tests for per-tenant graph routing.

    These tests exercise the full call chain through the HTTP stack:
        API key auth middleware
        → get_mcp_query_service() FastMCP Depends() dependency
        → TenantAwareQueryGraphRepository (existence check + query)
        → real PostgreSQL/AGE

    A regression that is invisible to the infrastructure-layer tests above
    (e.g., get_mcp_query_service() not reading tenant_id from the auth
    context, or _build_error_response dropping error_type) is caught here.

    No Keycloak is required.  API keys are inserted directly into the DB
    using the same schema as the IAM API key creation path.  The
    MCPApiKeyAuthMiddleware validates the key via bcrypt checkpw against
    the stored hash, then sets MCPAuthContext with the correct tenant_id.

    Spec: specs/query/query-execution.spec.md
      Requirement: Per-Tenant Graph Routing
        Scenario: Query routed to tenant graph
        Scenario: Tenant graph not found
    """

    @pytest.mark.asyncio
    async def test_query_executes_in_tenant_graph(
        self,
        async_http_client: AsyncClient,  # ensures app lifespan is running
        http_db_session: AsyncSession,
        tenant_a_id: str,
        tenant_b_id: str,
        integration_db_settings: DatabaseSettings,
        integration_connection_pool: ConnectionPool,
    ) -> None:
        """
        Spec Scenario: Query routed to tenant graph

        GIVEN an API key scoped to tenant_A
        AND tenant_A's AGE graph contains a unique Person node (Alice)
        AND tenant_B's AGE graph contains a different Person node (Bob)
        WHEN the MCP query_graph tool is called via HTTP with tenant_A's API key
        THEN only Alice is returned (tenant_A's data)
        AND Bob is absent (cross-tenant isolation enforced by the full stack)

        Full call chain exercised:
          X-API-Key header → MCPApiKeyAuthMiddleware validates key + sets
          MCPAuthContext(tenant_id=tenant_a_id) → get_mcp_query_service()
          reads tenant_id from context → TenantAwareQueryGraphRepository
          targets tenant_a_id's AGE graph → only tenant_A data is returned.
        """
        # --- Setup: create API key scoped to tenant_A ---
        api_key_secret = await _create_api_key_in_db(
            session=http_db_session,
            tenant_id=tenant_a_id,
            key_name=f"http-routing-test-a-{uuid.uuid4().hex[:6]}",
        )

        # --- Setup: provision both tenant graphs ---
        graph_a_name = f"tenant_{tenant_a_id}"
        graph_b_name = f"tenant_{tenant_b_id}"

        # Provision tenant_A's graph with a unique Person node
        _provision_age_graph_and_seed(
            settings=integration_db_settings,
            pool=integration_connection_pool,
            graph_name=graph_a_name,
            seed_cypher="CREATE (n:Person {name: 'Alice', tenant: 'A'})",
        )
        # Provision tenant_B's graph with a different Person node
        _provision_age_graph_and_seed(
            settings=integration_db_settings,
            pool=integration_connection_pool,
            graph_name=graph_b_name,
            seed_cypher="CREATE (n:Person {name: 'Bob', tenant: 'B'})",
        )

        try:
            # --- Exercise: call query_graph via the full HTTP/MCP stack ---
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
                        "cypher": "MATCH (n:Person) RETURN {name: n.name, tenant: n.tenant}"
                    },
                )

            # --- Assert: MCP protocol level must succeed ---
            assert result.is_error is False, (
                f"Expected a tool result, got an MCP protocol error: {result}"
            )

            tool_result = result.data

            # --- Assert: query executed successfully ---
            assert tool_result["success"] is True, (
                f"Expected success=True from tenant_A query, got: {tool_result}"
            )

            rows = tool_result["rows"]

            # Alice (tenant_A's data) MUST be present
            names = [row.get("name") for row in rows]
            assert "Alice" in names, (
                f"Expected tenant_A's 'Alice' node in results, "
                f"but names returned were: {names!r}. "
                f"Full rows: {rows}"
            )

            # Bob (tenant_B's data) MUST NOT appear — cross-tenant isolation
            assert "Bob" not in names, (
                f"Cross-tenant isolation violated: tenant_B's 'Bob' node "
                f"appeared in tenant_A query results. "
                f"This means get_mcp_query_service() is not correctly routing "
                f"to the authenticated tenant's graph. "
                f"Full rows: {rows}"
            )
        finally:
            # Teardown: drop both tenant graphs to avoid pollution
            _drop_graph_if_exists(integration_connection_pool, graph_a_name)
            _drop_graph_if_exists(integration_connection_pool, graph_b_name)

    @pytest.mark.asyncio
    async def test_tenant_graph_not_found_returns_structured_error(
        self,
        async_http_client: AsyncClient,  # ensures app lifespan is running
        http_db_session: AsyncSession,
        unprovisionied_tenant_id: str,
    ) -> None:
        """
        Spec Scenario: Tenant graph not found

        GIVEN an API key scoped to a tenant whose AGE graph has not been provisioned
        WHEN the MCP query_graph tool is called via HTTP with that API key
        THEN the HTTP response body contains success=False
        AND error_type is "execution_error"

        Full call chain exercised:
          X-API-Key header → MCPApiKeyAuthMiddleware validates key + sets
          MCPAuthContext(tenant_id=unprovisionied_tenant_id) →
          get_mcp_query_service() builds TenantAwareQueryGraphRepository →
          AGEGraphExistenceChecker finds no graph → QueryExecutionError raised →
          MCPQueryService returns QueryError(error_type="execution_error") →
          _build_error_response serialises it into the HTTP response body.

        A regression where _build_error_response drops error_type, or where
        get_mcp_query_service() does not propagate the tenant_id, would
        cause this test to fail even though the infrastructure-layer test passes.
        """
        # --- Setup: create API key scoped to the unprovisionied tenant ---
        api_key_secret = await _create_api_key_in_db(
            session=http_db_session,
            tenant_id=unprovisionied_tenant_id,
            key_name=f"http-routing-test-ghost-{uuid.uuid4().hex[:6]}",
        )
        # The AGE graph for unprovisionied_tenant_id is intentionally NOT created.

        # --- Exercise: call query_graph via the full HTTP/MCP stack ---
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": api_key_secret},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                {"cypher": "MATCH (n) RETURN n"},
            )

        # --- Assert: MCP protocol layer succeeds (no transport-level error) ---
        assert result.is_error is False, (
            f"Expected a tool result dict, got MCP protocol error: {result}"
        )

        tool_result = result.data

        # --- Assert: the tool returns a structured error (not a success) ---
        assert tool_result["success"] is False, (
            f"Expected success=False when tenant graph is not provisioned, "
            f"got: {tool_result}"
        )

        # --- Assert: the error_type is "execution_error" ---
        assert tool_result["error_type"] == "execution_error", (
            f"Expected error_type='execution_error' for missing tenant graph, "
            f"got: {tool_result.get('error_type')!r}. "
            f"Full response: {tool_result}"
        )
