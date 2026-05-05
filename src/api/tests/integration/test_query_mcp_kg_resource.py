"""Integration tests for the ``knowledge-graphs://accessible`` MCP resource.

Spec-Ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
Task-Ref: task-151

Tests the full HTTP stack:
  API key → MCPApiKeyAuthMiddleware → MCPAuthContext(user_id, tenant_id) →
  get_accessible_knowledge_graphs() resource → get_accessible_knowledge_graphs_for_mcp() →
  MCPKnowledgeGraphsService → AuthorizationProvider.lookup_resources() (SpiceDB) →
  IAccessibleKnowledgeGraphRepository.find_by_ids_and_tenant() (management DB) →
  JSON-encoded list of {id, name, description} returned to MCP client

Covered spec scenarios:

  Requirement: Knowledge Graphs Resource

  Scenario: List accessible knowledge graphs
    "GIVEN an authenticated MCP client
     WHEN the client reads the `knowledge_graphs://accessible` resource
     THEN the response contains all knowledge graphs the caller has `view`
     permission on within their tenant
     AND each entry includes the knowledge graph `id`, `name`, and `description`
     AND knowledge graphs the caller cannot access are omitted entirely"

  Scenario: No accessible knowledge graphs
    "GIVEN an authenticated MCP client with no accessible knowledge graphs
     WHEN the client reads the `knowledge_graphs://accessible` resource
     THEN an empty list is returned"

Design notes:
  - Uses direct DB insertions for API keys and KG records (no Keycloak dependency).
    The fake OIDC user IDs alice-test-id / bob-test-id are set up in the
    conftest's fake OIDC provider.
  - KG records are inserted directly into the ``knowledge_graphs`` table to avoid
    requiring a JWT auth flow for the management API.
  - SpiceDB viewer relationships are written in fixtures and cleaned up on teardown.
  - Each test class uses a unique KG name prefix to avoid unique-name constraint
    collisions across runs (the ``uq_knowledge_graphs_tenant_name`` constraint).
  - The MCP resource URI is ``knowledge-graphs://accessible`` (hyphen per RFC 3986;
    underscore is invalid in URI schemes).

Run with:
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_query_mcp_kg_resource.py \\
      -v -m integration
"""

from __future__ import annotations

import json
import uuid
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
from ulid import ULID

from iam.application.security import extract_prefix, generate_api_key_secret
from iam.domain.value_objects import APIKeyId
from infrastructure.authorization_dependencies import get_spicedb_client
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
    # Class-scoped loop so the LifespanManager's event loop outlives individual tests.
    pytest.mark.asyncio(loop_scope="class"),
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Fake OIDC pre-configured test user IDs (from tests/fakes/oidc_provider.py).
#: MCPApiKeyAuthMiddleware resolves user_id from the API key's created_by_user_id.
ALICE_USER_ID = "alice-test-id"

#: Unique prefixes so KG names don't collide with other test runs that may have
#: left rows behind (the uq_knowledge_graphs_tenant_name constraint is per-tenant).
_KG_PREFIX_VISIBLE = f"test-kg-visible-{uuid.uuid4().hex[:8]}"
_KG_PREFIX_HIDDEN = f"test-kg-hidden-{uuid.uuid4().hex[:8]}"
_KG_PREFIX_EMPTY = f"test-kg-empty-{uuid.uuid4().hex[:8]}"


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
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Start the Kartograph application once per test class.

    Class-scoped so the StreamableHTTPSessionManager (which cannot be restarted
    after its first ``run()`` call) stays alive across all tests in the class.
    The lifespan runs TenantBootstrapService, creating the default tenant.
    """
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def default_tenant_id(
    async_client: AsyncClient,
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


@pytest.fixture(scope="class")
def spicedb_client() -> AuthorizationProvider:
    """SpiceDB client for writing and cleaning up test relationships."""
    return get_spicedb_client()


# ---------------------------------------------------------------------------
# Helper: insert an API key directly into the DB (no Keycloak required)
# ---------------------------------------------------------------------------


async def _insert_api_key(
    integration_db_settings: DatabaseSettings,
    user_id: str,
    tenant_id: str,
    name_suffix: str,
) -> tuple[str, str]:
    """Insert an API key record and return (api_key_id, plaintext_secret).

    Uses bcrypt work factor 4 (vs. production factor 12) for test speed.
    MCPApiKeyAuthMiddleware resolves user_id from created_by_user_id.
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
                "user_id": user_id,
                "tenant_id": tenant_id,
                "name": f"{name_suffix}-{api_key_id[:8]}",
                "key_hash": key_hash,
                "prefix": prefix,
                "expires_at": expires_at,
            },
        )
        await session.commit()

    await engine.dispose()
    return api_key_id, secret


async def _delete_api_key(
    integration_db_settings: DatabaseSettings,
    api_key_id: str,
) -> None:
    """Remove an API key from the database."""
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
# Helper: insert a knowledge graph row directly in the management DB
# ---------------------------------------------------------------------------


async def _insert_knowledge_graph(
    integration_db_settings: DatabaseSettings,
    tenant_id: str,
    name: str,
    description: str,
) -> str:
    """Insert a knowledge graph row and return its ID (ULID string).

    Inserts directly into ``knowledge_graphs`` to avoid needing JWT auth for
    the management API. The root workspace ID is used as the workspace_id.
    """
    engine = create_write_engine(integration_db_settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    kg_id = str(ULID())

    # Find the root workspace for this tenant
    async with session_factory() as session:
        result = await session.execute(
            text(
                "SELECT id FROM workspaces WHERE tenant_id = :tenant_id AND is_root = true"
            ),
            {"tenant_id": tenant_id},
        )
        workspace_id = result.scalar_one_or_none()

        if workspace_id is None:
            # Fallback: use any workspace in the tenant
            result = await session.execute(
                text("SELECT id FROM workspaces WHERE tenant_id = :tenant_id LIMIT 1"),
                {"tenant_id": tenant_id},
            )
            workspace_id = result.scalar_one_or_none()

        assert workspace_id is not None, (
            f"No workspace found for tenant {tenant_id}. "
            "Ensure app lifespan ran (the default workspace is created at startup)."
        )

        await session.execute(
            text("""
                INSERT INTO knowledge_graphs
                    (id, tenant_id, workspace_id, name, description, created_at, updated_at)
                VALUES
                    (:id, :tenant_id, :workspace_id, :name, :description, now(), now())
            """),
            {
                "id": kg_id,
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "name": name,
                "description": description,
            },
        )
        await session.commit()

    await engine.dispose()
    return kg_id


async def _delete_knowledge_graph(
    integration_db_settings: DatabaseSettings,
    kg_id: str,
) -> None:
    """Remove a knowledge graph row from the database."""
    engine = create_write_engine(integration_db_settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM knowledge_graphs WHERE id = :id"),
            {"id": kg_id},
        )
        await session.commit()
    await engine.dispose()


# ===========================================================================
# Test class 1: List accessible knowledge graphs
# ===========================================================================
#
# Spec: "GIVEN an authenticated MCP client
#        WHEN the client reads the knowledge_graphs://accessible resource
#        THEN the response contains all knowledge graphs the caller has view
#        permission on within their tenant
#        AND each entry includes the knowledge graph id, name, and description
#        AND knowledge graphs the caller cannot access are omitted entirely"
# ===========================================================================


class TestKnowledgeGraphsResourceListsAccessible:
    """Integration tests for the "List accessible knowledge graphs" scenario.

    Setup:
    - Two KG records in the default tenant's DB:
        * kg_visible_id — SpiceDB viewer relation GRANTED for alice
        * kg_hidden_id  — NO SpiceDB relation (alice cannot access)
    - One API key for alice in the default tenant.
    - alice reads the resource → only kg_visible_id is returned.
    """

    @pytest_asyncio.fixture(scope="class", loop_scope="class")
    async def kg_visible_id(
        self,
        async_client: AsyncClient,
        integration_db_settings: DatabaseSettings,
        default_tenant_id: str,
    ) -> AsyncGenerator[str, None]:
        """Insert the visible KG (alice will have VIEW) and clean up afterward."""
        kg_id = await _insert_knowledge_graph(
            integration_db_settings,
            tenant_id=default_tenant_id,
            name=f"{_KG_PREFIX_VISIBLE}-visible",
            description="The knowledge graph alice can view",
        )
        yield kg_id
        await _delete_knowledge_graph(integration_db_settings, kg_id)

    @pytest_asyncio.fixture(scope="class", loop_scope="class")
    async def kg_hidden_id(
        self,
        async_client: AsyncClient,
        integration_db_settings: DatabaseSettings,
        default_tenant_id: str,
    ) -> AsyncGenerator[str, None]:
        """Insert the hidden KG (alice has NO VIEW permission) and clean up."""
        kg_id = await _insert_knowledge_graph(
            integration_db_settings,
            tenant_id=default_tenant_id,
            name=f"{_KG_PREFIX_HIDDEN}-hidden",
            description="The knowledge graph alice cannot view",
        )
        yield kg_id
        await _delete_knowledge_graph(integration_db_settings, kg_id)

    @pytest_asyncio.fixture(scope="class", loop_scope="class")
    async def alice_viewer_on_visible_kg(
        self,
        spicedb_client: AuthorizationProvider,
        kg_visible_id: str,
    ) -> AsyncGenerator[None, None]:
        """Grant alice viewer on kg_visible_id; clean up on teardown.

        Writes:  knowledge_graph:<kg_visible_id>#viewer@user:alice-test-id
        """
        resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_visible_id)
        subject = format_subject(ResourceType.USER, ALICE_USER_ID)

        await spicedb_client.write_relationship(
            resource=resource,
            relation="viewer",
            subject=subject,
        )

        yield

        try:
            await spicedb_client.delete_relationship(
                resource=resource,
                relation="viewer",
                subject=subject,
            )
        except Exception:
            pass

    @pytest_asyncio.fixture(scope="class", loop_scope="class")
    async def alice_api_key_visible(
        self,
        async_client: AsyncClient,
        integration_db_settings: DatabaseSettings,
        default_tenant_id: str,
    ) -> AsyncGenerator[str, None]:
        """Insert an API key for alice scoped to the default tenant.

        Returns the plaintext secret for use as the X-API-Key header.
        """
        api_key_id, secret = await _insert_api_key(
            integration_db_settings,
            user_id=ALICE_USER_ID,
            tenant_id=default_tenant_id,
            name_suffix="alice-kg-visible",
        )
        yield secret
        await _delete_api_key(integration_db_settings, api_key_id)

    async def test_accessible_kgs_returns_only_permitted_kg(
        self,
        async_client: AsyncClient,
        alice_api_key_visible: str,
        kg_visible_id: str,
        kg_hidden_id: str,
        alice_viewer_on_visible_kg: None,
    ) -> None:
        """Reading knowledge-graphs://accessible returns only the KG alice has VIEW on.

        Spec: "THEN the response contains all knowledge graphs the caller has view
               permission on within their tenant
               AND knowledge graphs the caller cannot access are omitted entirely"

        alice has viewer on kg_visible_id but NOT on kg_hidden_id.  The resource
        must return only kg_visible_id.
        """
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": alice_api_key_visible},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            contents = await mcp_client.read_resource("knowledge-graphs://accessible")

        assert len(contents) == 1, (
            f"Expected exactly one content block from the resource, got {len(contents)}"
        )

        raw = contents[0].text  # type: ignore[union-attr]
        result = json.loads(raw)

        assert isinstance(result, list), (
            f"Expected a JSON list from the resource, got: {type(result)}"
        )

        returned_ids = {entry["id"] for entry in result}

        assert kg_visible_id in returned_ids, (
            f"Expected kg_visible_id={kg_visible_id!r} in returned IDs, "
            f"but got: {returned_ids}"
        )
        assert kg_hidden_id not in returned_ids, (
            f"kg_hidden_id={kg_hidden_id!r} MUST be omitted (alice has no VIEW), "
            f"but it appeared in: {returned_ids}"
        )

    async def test_accessible_kg_entry_includes_id_name_description(
        self,
        async_client: AsyncClient,
        alice_api_key_visible: str,
        kg_visible_id: str,
        kg_hidden_id: str,
        alice_viewer_on_visible_kg: None,
        integration_db_settings: DatabaseSettings,
        default_tenant_id: str,
    ) -> None:
        """Each entry in the resource response includes id, name, and description.

        Spec: "AND each entry includes the knowledge graph id, name, and description"
        """
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": alice_api_key_visible},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            contents = await mcp_client.read_resource("knowledge-graphs://accessible")

        raw = contents[0].text  # type: ignore[union-attr]
        result = json.loads(raw)

        # Find the visible KG entry
        visible_entry = next(
            (entry for entry in result if entry["id"] == kg_visible_id),
            None,
        )

        assert visible_entry is not None, (
            f"Expected an entry with id={kg_visible_id!r}, got: {result}"
        )
        assert "id" in visible_entry, f"Entry missing 'id' field: {visible_entry}"
        assert "name" in visible_entry, f"Entry missing 'name' field: {visible_entry}"
        assert "description" in visible_entry, (
            f"Entry missing 'description' field: {visible_entry}"
        )
        assert visible_entry["id"] == kg_visible_id
        assert visible_entry["name"] == f"{_KG_PREFIX_VISIBLE}-visible"
        assert visible_entry["description"] == "The knowledge graph alice can view"

    async def test_inaccessible_kg_omitted_entirely(
        self,
        async_client: AsyncClient,
        alice_api_key_visible: str,
        kg_visible_id: str,
        kg_hidden_id: str,
        alice_viewer_on_visible_kg: None,
    ) -> None:
        """KGs the caller cannot access must not appear in the response at all.

        Spec: "AND knowledge graphs the caller cannot access are omitted entirely"

        This is a separate, focused assertion for the omission requirement.
        """
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": alice_api_key_visible},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            contents = await mcp_client.read_resource("knowledge-graphs://accessible")

        raw = contents[0].text  # type: ignore[union-attr]
        result = json.loads(raw)

        returned_ids = {entry["id"] for entry in result}
        assert kg_hidden_id not in returned_ids, (
            f"HIDDEN KG {kg_hidden_id!r} must be omitted entirely — "
            f"alice has no VIEW permission. Returned IDs: {returned_ids}"
        )


# ===========================================================================
# Test class 2: No accessible knowledge graphs
# ===========================================================================
#
# Spec: "GIVEN an authenticated MCP client with no accessible knowledge graphs
#        WHEN the client reads the knowledge_graphs://accessible resource
#        THEN an empty list is returned"
# ===========================================================================


class TestKnowledgeGraphsResourceEmpty:
    """Integration tests for the "No accessible knowledge graphs" scenario.

    Setup:
    - One KG record in the default tenant's DB (kg_no_perm_id).
    - NO SpiceDB viewer relationship is written for alice on this KG.
    - One API key for alice in the default tenant.
    - alice reads the resource → empty list.
    """

    @pytest_asyncio.fixture(scope="class", loop_scope="class")
    async def kg_no_perm_id(
        self,
        async_client: AsyncClient,
        integration_db_settings: DatabaseSettings,
        default_tenant_id: str,
    ) -> AsyncGenerator[str, None]:
        """Insert a KG that alice has NO permission on; clean up afterward."""
        kg_id = await _insert_knowledge_graph(
            integration_db_settings,
            tenant_id=default_tenant_id,
            name=f"{_KG_PREFIX_EMPTY}-no-perm",
            description="A KG with no permissions granted to alice",
        )
        yield kg_id
        await _delete_knowledge_graph(integration_db_settings, kg_id)

    @pytest_asyncio.fixture(scope="class", loop_scope="class")
    async def alice_api_key_empty(
        self,
        async_client: AsyncClient,
        integration_db_settings: DatabaseSettings,
        default_tenant_id: str,
    ) -> AsyncGenerator[str, None]:
        """Insert an API key for alice scoped to the default tenant."""
        api_key_id, secret = await _insert_api_key(
            integration_db_settings,
            user_id=ALICE_USER_ID,
            tenant_id=default_tenant_id,
            name_suffix="alice-kg-empty",
        )
        yield secret
        await _delete_api_key(integration_db_settings, api_key_id)

    async def test_resource_returns_empty_list_when_no_permissions(
        self,
        async_client: AsyncClient,
        alice_api_key_empty: str,
        kg_no_perm_id: str,
    ) -> None:
        """Resource returns an empty list when alice has no VIEW on any KG.

        Spec: "GIVEN an authenticated MCP client with no accessible knowledge graphs
               WHEN the client reads the knowledge_graphs://accessible resource
               THEN an empty list is returned"

        The KG exists in the DB (kg_no_perm_id), but no SpiceDB viewer
        relationship is written for alice.  SpiceDB.lookup_resources returns [],
        MCPKnowledgeGraphsService short-circuits and returns [], and the resource
        returns ``[]``.
        """
        async with Client(
            StreamableHttpTransport(
                url="http://test/query/mcp",
                headers={"X-API-Key": alice_api_key_empty},
                httpx_client_factory=_make_asgi_httpx_factory(app),
            )
        ) as mcp_client:
            contents = await mcp_client.read_resource("knowledge-graphs://accessible")

        assert len(contents) == 1, (
            f"Expected exactly one content block from the resource, got {len(contents)}"
        )

        raw = contents[0].text  # type: ignore[union-attr]
        result = json.loads(raw)

        assert result == [], (
            f"Expected empty list when alice has no VIEW permissions, but got: {result}"
        )
