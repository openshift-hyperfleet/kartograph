"""Integration tests for MCP secure enclave entity redaction at the HTTP transport layer.

Spec-Ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
Task-Ref: task-133

Tests the full HTTP stack:
  API key → MCPApiKeyAuthMiddleware → MCPAuthContext(user_id) →
  query_graph tool → MCPQueryService → TenantAwareQueryGraphRepository →
  AGE graph → MCPQuerySecureEnclave.apply_redaction() → SpiceDB check →
  redacted / full results returned to client

Covered spec scenario:
  Requirement: Graph Query Tool — Scenario: Secure enclave redaction
    "GIVEN query results containing entities the caller is not authorized to view
     WHEN the results are returned
     THEN unauthorized nodes are redacted to ID-only (all other properties stripped)
     AND unauthorized edges are redacted to their ID, start_id, and end_id only
       (all other properties stripped)
     AND the graph topology (which entities exist and are connected) is preserved"

Design notes:
  - Uses direct DB API key insertion (no Keycloak) with pre-configured fake OIDC
    test user IDs: alice ("alice-test-id") and bob ("bob-test-id").
  - alice is granted SpiceDB `viewer` relation on KG_RESTRICTED_ID.
  - bob has NO SpiceDB relation on KG_RESTRICTED_ID.
  - Nodes/edges are inserted into the tenant's AGE graph (tenant_{tenant_id}) with
    ``knowledge_graph_id = KG_RESTRICTED_ID`` in their properties.
  - Each call uses ``knowledge_graph_id=KG_RESTRICTED_ID`` in the tool parameters so
    only test nodes are returned — isolating the test from other graph data.
  - SpiceDB relationships and API keys are cleaned up in fixture teardown to
    prevent cross-test pollution.

Run with:
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_secure_enclave_mcp.py -v -m integration
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
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings
from main import app
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    ResourceType,
    format_resource,
    format_subject,
)

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

#: Fake OIDC pre-configured test user IDs (from tests/fakes/oidc_provider.py).
#: MCPApiKeyAuthMiddleware resolves user_id from the API key's created_by_user_id.
ALICE_USER_ID = "alice-test-id"
BOB_USER_ID = "bob-test-id"

#: A unique KG ID used only by this test file to isolate test data.
#: Alice will have VIEW on this KG; bob will not.
KG_RESTRICTED_ID = "kg-restricted-enclave-test"


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

    Class-scoped so that the ``StreamableHTTPSessionManager`` (which cannot
    be restarted after its first ``run()`` call) stays alive across all tests
    in the class.  The lifespan runs TenantBootstrapService, which creates
    the default tenant on first startup.

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
async def enclave_tenant_id(
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
# Fixtures: AGE graph provisioning and node insertion
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="class")
async def provisioned_enclave_graph(
    async_client: AsyncClient,
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
    enclave_tenant_id: str,
) -> AsyncGenerator[AgeGraphClient, None]:
    """Provision the tenant AGE graph and return a connected AgeGraphClient.

    The graph name is ``tenant_{enclave_tenant_id}``, matching the routing used
    by TenantAwareQueryGraphRepository for the default tenant.

    Pre-cleanup removes any nodes tagged with KG_RESTRICTED_ID left over from
    a previous interrupted test run (safety net; normal teardown handles it).
    Post-cleanup removes nodes inserted during this test.
    """
    factory = ConnectionFactory(
        integration_db_settings, pool=integration_connection_pool
    )
    graph_name = f"tenant_{enclave_tenant_id}"

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
        tenant_client.execute_cypher(
            f"MATCH (n {{knowledge_graph_id: '{KG_RESTRICTED_ID}'}}) DETACH DELETE n"
        )
    except Exception:
        pass

    yield tenant_client

    # Post-cleanup: remove nodes inserted during this test
    try:
        tenant_client.execute_cypher(
            f"MATCH (n {{knowledge_graph_id: '{KG_RESTRICTED_ID}'}}) DETACH DELETE n"
        )
    except Exception:
        pass

    tenant_client.disconnect()


# ---------------------------------------------------------------------------
# Fixtures: API key insertion (direct DB, no Keycloak)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def alice_api_key(
    async_client: AsyncClient,  # ensures app started → tenant exists in DB
    integration_db_settings: DatabaseSettings,
    enclave_tenant_id: str,
) -> AsyncGenerator[str, None]:
    """Insert an API key for alice (user_id='alice-test-id') and return the secret.

    Alice is the authorized caller — the kg_view_for_alice fixture grants her
    SpiceDB VIEW on KG_RESTRICTED_ID.

    MCPApiKeyAuthMiddleware resolves user_id from created_by_user_id, so
    MCPAuthContext.user_id will be ALICE_USER_ID when alice's key is used.

    Class-scoped so the same key is reused across all tests in the class; one
    insert/delete per class instead of one per test.

    Uses bcrypt work factor 4 (vs. production factor 12) for test speed;
    bcrypt.checkpw() respects the cost stored in the hash.
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
                "tenant_id": enclave_tenant_id,
                "name": f"alice-enclave-{api_key_id[:8]}",
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


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def bob_api_key(
    async_client: AsyncClient,  # ensures app started → tenant exists in DB
    integration_db_settings: DatabaseSettings,
    enclave_tenant_id: str,
) -> AsyncGenerator[str, None]:
    """Insert an API key for bob (user_id='bob-test-id') and return the secret.

    Bob is the unauthorized caller — he has NO SpiceDB VIEW on KG_RESTRICTED_ID.

    Class-scoped so the same key is reused across all tests in the class.

    Uses bcrypt work factor 4 (vs. production factor 12) for test speed.
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
                "user_id": BOB_USER_ID,
                "tenant_id": enclave_tenant_id,
                "name": f"bob-enclave-{api_key_id[:8]}",
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
# Fixtures: SpiceDB relationships
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def spicedb_client() -> AuthorizationProvider:
    """SpiceDB client for writing and cleaning up test relationships."""
    return get_spicedb_client()


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def kg_view_for_alice(
    spicedb_client: AuthorizationProvider,
) -> AsyncGenerator[None, None]:
    """Grant alice VIEW on KG_RESTRICTED_ID via SpiceDB; remove it on teardown.

    Writes the relationship::

        knowledge_graph:kg-restricted-enclave-test#viewer@user:alice-test-id

    MCPQuerySecureEnclave checks this permission via::

        check_permission(
            resource="knowledge_graph:kg-restricted-enclave-test",
            permission="view",
            subject="user:alice-test-id",
        )

    bob has NO matching relationship → his nodes/edges are redacted.
    """
    resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, KG_RESTRICTED_ID)
    subject = format_subject(ResourceType.USER, ALICE_USER_ID)

    await spicedb_client.write_relationship(
        resource=resource,
        relation="viewer",
        subject=subject,
    )

    yield

    # Teardown: remove the relationship to prevent cross-test pollution
    try:
        await spicedb_client.delete_relationship(
            resource=resource,
            relation="viewer",
            subject=subject,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSecureEnclaveRedactionIntegration:
    """Integration tests for MCP secure enclave entity redaction.

    Tests the full chain:
      API key → MCPApiKeyAuthMiddleware → MCPAuthContext(user_id) →
      query_graph tool → MCPQueryService → TenantAwareQueryGraphRepository →
      AGE graph → MCPQuerySecureEnclave.apply_redaction() → SpiceDB check →
      redacted (bob) / full (alice) results

    Spec-Ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
    Requirement: Graph Query Tool — Scenario: Secure enclave redaction
    """

    async def test_unauthorized_nodes_redacted_to_id_only(
        self,
        async_client: AsyncClient,
        bob_api_key: str,
        kg_view_for_alice: None,
        provisioned_enclave_graph: AgeGraphClient,
    ) -> None:
        """Unauthorized caller receives nodes redacted with label and _redacted flag.

        Spec: "GIVEN query results containing entities the caller is not authorized to view
               WHEN the results are returned
               THEN unauthorized nodes are redacted (properties stripped, label and
               _redacted flag preserved for topology context)"

        bob has NO viewer relation on KG_RESTRICTED_ID → all nodes are redacted to
        ``{"id": "...", "label": "...", "_redacted": true}`` with optional domainId.
        """
        # Insert 2 Person nodes stamped with the restricted KG
        provisioned_enclave_graph.execute_cypher(
            f"CREATE (p:Person {{name: 'AlicePerson', "
            f"knowledge_graph_id: '{KG_RESTRICTED_ID}'}})"
        )
        provisioned_enclave_graph.execute_cypher(
            f"CREATE (p:Person {{name: 'BobPerson', "
            f"knowledge_graph_id: '{KG_RESTRICTED_ID}'}})"
        )

        # Bob calls query_graph — KG scoping via WHERE clause
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": bob_api_key},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                {
                    "cypher": (
                        f"MATCH (n:Person) WHERE n.knowledge_graph_id = "
                        f"'{KG_RESTRICTED_ID}' RETURN n LIMIT 10"
                    ),
                },
            )

        assert result.is_error is False, f"MCP protocol error: {result}"
        tool_result = result.data

        assert tool_result["success"] is True, (
            f"Expected success=True, got: {tool_result}"
        )

        rows = tool_result["rows"]
        assert len(rows) == 2, (
            f"Expected exactly 2 rows (2 nodes inserted with KG_RESTRICTED_ID), "
            f"got {len(rows)}.  Rows: {rows}"
        )

        for row in rows:
            node = row["node"]
            # Redacted nodes include id, label, _redacted, and optionally domainId
            assert "id" in node, f"Redacted node must have 'id' — got: {node}"
            assert "label" in node, f"Redacted node must have 'label' — got: {node}"
            assert node.get("_redacted") is True, (
                f"Redacted node must have '_redacted': true — got: {node}"
            )
            assert "properties" not in node, (
                f"Redacted node must NOT have 'properties' — got: {node}"
            )
            # Only id, label, _redacted, and optionally domainId are allowed
            allowed_keys = {"id", "label", "_redacted", "domainId"}
            assert set(node.keys()) <= allowed_keys, (
                f"Unauthorized node has unexpected keys — "
                f"got keys: {set(node.keys())}, allowed: {allowed_keys}.  Full node: {node}"
            )

    async def test_unauthorized_edges_redacted_to_structural_fields_only(
        self,
        async_client: AsyncClient,
        bob_api_key: str,
        kg_view_for_alice: None,
        provisioned_enclave_graph: AgeGraphClient,
    ) -> None:
        """Unauthorized caller receives edges redacted with label, topology, and _redacted flag.

        Spec: "AND unauthorized edges are redacted to their structural fields
               (id, label, start_id, end_id, _redacted) with properties stripped"

        bob has NO viewer relation on KG_RESTRICTED_ID → the KNOWS edge is redacted to
        ``{"id": "...", "label": "...", "start_id": "...", "end_id": "...", "_redacted": true}``
        with optional domainId.
        """
        # Insert two Person nodes and a KNOWS edge, all stamped with the restricted KG
        provisioned_enclave_graph.execute_cypher(
            f"CREATE "
            f"(a:Person {{name: 'PersonA', knowledge_graph_id: '{KG_RESTRICTED_ID}'}})"
            f"-[:KNOWS {{since: 2020, knowledge_graph_id: '{KG_RESTRICTED_ID}'}}]->"
            f"(b:Person {{name: 'PersonB', knowledge_graph_id: '{KG_RESTRICTED_ID}'}})"
        )

        # Bob calls query_graph — KG scoping via WHERE clause on edge properties
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": bob_api_key},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                {
                    "cypher": (
                        f"MATCH (a)-[r:KNOWS]->(b) "
                        f"WHERE r.knowledge_graph_id = '{KG_RESTRICTED_ID}' "
                        f"RETURN r LIMIT 10"
                    ),
                },
            )

        assert result.is_error is False, f"MCP protocol error: {result}"
        tool_result = result.data

        assert tool_result["success"] is True, (
            f"Expected success=True, got: {tool_result}"
        )

        rows = tool_result["rows"]
        assert len(rows) == 1, (
            f"Expected exactly 1 edge row, got {len(rows)}.  Rows: {rows}"
        )

        edge = rows[0]["edge"]
        # Redacted edges include id, label, start_id, end_id, _redacted, and optionally domainId
        assert "id" in edge, f"Redacted edge must have 'id' — got: {edge}"
        assert "label" in edge, f"Redacted edge must have 'label' — got: {edge}"
        assert "start_id" in edge, f"Redacted edge must have 'start_id' — got: {edge}"
        assert "end_id" in edge, f"Redacted edge must have 'end_id' — got: {edge}"
        assert edge.get("_redacted") is True, (
            f"Redacted edge must have '_redacted': true — got: {edge}"
        )
        assert "properties" not in edge, (
            f"Redacted edge must NOT have 'properties' — got: {edge}"
        )
        # Only structural fields and redaction metadata are allowed
        allowed_keys = {"id", "label", "start_id", "end_id", "_redacted", "domainId"}
        assert set(edge.keys()) <= allowed_keys, (
            f"Unauthorized edge has unexpected keys — "
            f"got keys: {set(edge.keys())}, allowed: {allowed_keys}.  Full edge: {edge}"
        )

    async def test_graph_topology_preserved_for_unauthorized_caller(
        self,
        async_client: AsyncClient,
        bob_api_key: str,
        kg_view_for_alice: None,
        provisioned_enclave_graph: AgeGraphClient,
    ) -> None:
        """Topology is preserved: all rows returned, just redacted for unauthorized callers.

        Spec: "AND the graph topology (which entities exist and are connected) is preserved"

        Insert 3 Person nodes; bob's query returns 3 rows — the entities are NOT filtered
        out, only their properties are stripped. Each row carries a redacted node
        ``{"id": "...", "label": "...", "_redacted": true}`` so the caller knows the
        entity exists and its type.
        """
        # Insert 3 Person nodes stamped with the restricted KG
        for i in range(3):
            provisioned_enclave_graph.execute_cypher(
                f"CREATE (p:Person {{name: 'TopologyPerson{i}', "
                f"knowledge_graph_id: '{KG_RESTRICTED_ID}'}})"
            )

        # Bob calls query_graph — KG scoping via WHERE clause
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": bob_api_key},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                {
                    "cypher": (
                        f"MATCH (n:Person) WHERE n.knowledge_graph_id = "
                        f"'{KG_RESTRICTED_ID}' RETURN n LIMIT 100"
                    ),
                },
            )

        assert result.is_error is False, f"MCP protocol error: {result}"
        tool_result = result.data

        assert tool_result["success"] is True, (
            f"Expected success=True, got: {tool_result}"
        )

        rows = tool_result["rows"]
        # All 3 nodes MUST be present — topology preserved even for unauthorized callers
        assert len(rows) == 3, (
            f"Expected exactly 3 rows (topology preserved), got {len(rows)}.  "
            f"Rows: {rows}"
        )

        # Each row must be redacted with label and _redacted flag
        for row in rows:
            node = row["node"]
            assert "id" in node, f"Redacted node must have 'id' — got: {node}"
            assert "label" in node, f"Redacted node must have 'label' — got: {node}"
            assert node.get("_redacted") is True, (
                f"Redacted node must have '_redacted': true — got: {node}"
            )
            assert "properties" not in node, (
                f"Topology-preserved rows must be redacted (no 'properties') — "
                f"got keys: {set(node.keys())}.  Full node: {node}"
            )

    async def test_authorized_caller_receives_full_properties(
        self,
        async_client: AsyncClient,
        alice_api_key: str,
        kg_view_for_alice: None,
        provisioned_enclave_graph: AgeGraphClient,
    ) -> None:
        """Authorized caller receives full node properties (positive control).

        Spec: Implicit — the secure enclave ONLY redacts for unauthorized callers;
              authorized callers receive the full entity with label and properties.

        alice has VIEW on KG_RESTRICTED_ID → nodes are NOT redacted; they carry
        ``{"id": ..., "label": ..., "properties": {...}}``.
        """
        # Insert 2 Person nodes stamped with the restricted KG
        provisioned_enclave_graph.execute_cypher(
            f"CREATE (p:Person {{name: 'AuthorizedPersonA', "
            f"knowledge_graph_id: '{KG_RESTRICTED_ID}'}})"
        )
        provisioned_enclave_graph.execute_cypher(
            f"CREATE (p:Person {{name: 'AuthorizedPersonB', "
            f"knowledge_graph_id: '{KG_RESTRICTED_ID}'}})"
        )

        # Alice calls query_graph — KG scoping via WHERE clause
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": alice_api_key},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            result = await mcp_client.call_tool(
                "query_graph",
                {
                    "cypher": (
                        f"MATCH (n:Person) WHERE n.knowledge_graph_id = "
                        f"'{KG_RESTRICTED_ID}' RETURN n LIMIT 10"
                    ),
                },
            )

        assert result.is_error is False, f"MCP protocol error: {result}"
        tool_result = result.data

        assert tool_result["success"] is True, (
            f"Expected success=True, got: {tool_result}"
        )

        rows = tool_result["rows"]
        assert len(rows) == 2, (
            f"Expected exactly 2 rows for alice, got {len(rows)}.  Rows: {rows}"
        )

        for row in rows:
            node = row["node"]
            assert "label" in node, (
                "Authorized caller should receive nodes with 'label' field — "
                f"got keys: {set(node.keys())}.  Full node: {node}"
            )
            assert "properties" in node, (
                "Authorized caller should receive nodes with 'properties' field — "
                f"got keys: {set(node.keys())}.  Full node: {node}"
            )
            # Verify the knowledge_graph_id is present in the returned properties
            assert node["properties"].get("knowledge_graph_id") == KG_RESTRICTED_ID, (
                "Node properties should include knowledge_graph_id — "
                f"got properties: {node.get('properties')}"
            )
