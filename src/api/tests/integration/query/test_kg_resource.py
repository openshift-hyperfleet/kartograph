"""Integration tests for the knowledge-graphs://accessible MCP resource.

Exercises the full stack from MCPKnowledgeGraphsService through SpiceDB
(``lookup_resources``) and the Management DB (``knowledge_graphs`` table)
against real infrastructure.

Spec-Ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
Task-Ref: task-110

Scenarios covered:
  - Requirement: Knowledge Graphs Resource / List accessible knowledge graphs
      Given an authenticated caller with ``view`` on KG-1 (but NOT KG-2),
      when the resource is read, KG-1 appears and KG-2 is absent.
  - Requirement: Knowledge Graphs Resource / No accessible knowledge graphs
      Given an authenticated caller with NO permissions, when the resource
      is read, an empty list is returned (not an error).

Design notes:
  These tests exercise the two integration points that unit tests cannot cover:
    1. SpiceDB ``lookup_resources`` → real gRPC round-trip
    2. Management DB query → real PostgreSQL round-trip

  The ``MCPKnowledgeGraphsService`` is instantiated directly with real
  collaborators (SpiceDB client + repository backed by the Management DB).
  ``_ManagementKnowledgeGraphRepository`` is used as-is from the composition
  layer so the test exercises the same code path as the live MCP resource.

  SpiceDB relationships written during setup are cleaned up in an autouse
  fixture to prevent cross-test pollution in the SpiceDB store.

Run with:
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/query/test_kg_resource.py -v -m integration
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings
from pydantic import SecretStr
from query.application.kg_service import MCPKnowledgeGraphsService
from query.domain.value_objects import AccessibleKnowledgeGraph
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    ResourceType,
    format_resource,
    format_subject,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures: database settings and session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def kg_db_settings() -> DatabaseSettings:
    """Database settings for the KG resource integration tests."""
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
async def async_session(
    kg_db_settings: DatabaseSettings,
) -> AsyncGenerator[AsyncSession, None]:
    """Async SQLAlchemy session for Management DB access."""
    engine = create_write_engine(kg_db_settings)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Fixtures: SpiceDB client
# ---------------------------------------------------------------------------


@pytest.fixture
def spicedb() -> AuthorizationProvider:
    """SpiceDB client for writing and cleaning up test relationships."""
    return get_spicedb_client()


# ---------------------------------------------------------------------------
# Fixtures: test tenant / workspace / knowledge graphs
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_tenant_id(
    async_session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Create an isolated test tenant and clean it up after the test.

    Uses raw SQL to avoid importing IAM domain objects and to stay light.
    Returns the new tenant's ID (ULID string).
    """
    tenant_id = f"test-tenant-{uuid.uuid4().hex[:12]}"
    tenant_name = f"kg-resource-test-tenant-{tenant_id}"

    await async_session.execute(
        text(
            "INSERT INTO tenants (id, name, created_at, updated_at) "
            "VALUES (:id, :name, NOW(), NOW())"
        ),
        {"id": tenant_id, "name": tenant_name},
    )
    await async_session.commit()

    yield tenant_id

    # Teardown
    try:
        await async_session.execute(
            text("DELETE FROM knowledge_graphs WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        await async_session.execute(
            text("DELETE FROM workspaces WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        await async_session.execute(
            text("DELETE FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        )
        await async_session.commit()
    except (ProgrammingError, Exception):
        await async_session.rollback()


@pytest_asyncio.fixture
async def test_workspace_id(
    async_session: AsyncSession,
    test_tenant_id: str,
) -> AsyncGenerator[str, None]:
    """Create a root workspace for the test tenant.

    Returns the new workspace's ID.
    """
    workspace_id = f"test-ws-{uuid.uuid4().hex[:12]}"

    await async_session.execute(
        text(
            "INSERT INTO workspaces "
            "(id, tenant_id, name, is_root, created_at, updated_at) "
            "VALUES (:id, :tenant_id, :name, :is_root, NOW(), NOW())"
        ),
        {
            "id": workspace_id,
            "tenant_id": test_tenant_id,
            "name": f"test-ws-{workspace_id}",
            "is_root": True,
        },
    )
    await async_session.commit()

    yield workspace_id


@pytest_asyncio.fixture
async def kg1_id(
    async_session: AsyncSession,
    test_tenant_id: str,
    test_workspace_id: str,
) -> AsyncGenerator[str, None]:
    """Create Knowledge Graph 1 (to be permitted for the test user).

    Returns the KG's ID.
    """
    kg_id = f"test-kg1-{uuid.uuid4().hex[:12]}"

    await async_session.execute(
        text(
            "INSERT INTO knowledge_graphs "
            "(id, tenant_id, workspace_id, name, description, created_at, updated_at) "
            "VALUES (:id, :tenant_id, :workspace_id, :name, :desc, NOW(), NOW())"
        ),
        {
            "id": kg_id,
            "tenant_id": test_tenant_id,
            "workspace_id": test_workspace_id,
            "name": "KG One",
            "desc": "First test knowledge graph",
        },
    )
    await async_session.commit()

    yield kg_id


@pytest_asyncio.fixture
async def kg2_id(
    async_session: AsyncSession,
    test_tenant_id: str,
    test_workspace_id: str,
) -> AsyncGenerator[str, None]:
    """Create Knowledge Graph 2 (to be denied for the test user).

    Returns the KG's ID.
    """
    kg_id = f"test-kg2-{uuid.uuid4().hex[:12]}"

    await async_session.execute(
        text(
            "INSERT INTO knowledge_graphs "
            "(id, tenant_id, workspace_id, name, description, created_at, updated_at) "
            "VALUES (:id, :tenant_id, :workspace_id, :name, :desc, NOW(), NOW())"
        ),
        {
            "id": kg_id,
            "tenant_id": test_tenant_id,
            "workspace_id": test_workspace_id,
            "name": "KG Two",
            "desc": "Second test knowledge graph (inaccessible)",
        },
    )
    await async_session.commit()

    yield kg_id


# ---------------------------------------------------------------------------
# Fixtures: unique test user
# ---------------------------------------------------------------------------


@pytest.fixture
def test_user_id() -> str:
    """A unique user ID for each test to prevent cross-test SpiceDB pollution."""
    return f"test-user-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Fixture: SpiceDB teardown (autouse per test class)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def cleanup_kg1_view(
    spicedb: AuthorizationProvider,
    test_user_id: str,
    kg1_id: str,
) -> AsyncGenerator[None, None]:
    """Remove the KG-1 view relationship from SpiceDB after the test.

    Autouse is NOT used here because only the test that writes this
    relationship needs the teardown. Call this fixture explicitly where needed.
    """
    yield

    try:
        await spicedb.delete_relationship(
            resource=format_resource(ResourceType.KNOWLEDGE_GRAPH, kg1_id),
            relation="viewer",
            subject=format_subject(ResourceType.USER, test_user_id),
        )
    except Exception:
        pass  # Relationship may not exist if test did not create it


# ---------------------------------------------------------------------------
# Helper: build the service under test
# ---------------------------------------------------------------------------


def _make_service(
    spicedb: AuthorizationProvider,
    session: AsyncSession,
    user_id: str,
    tenant_id: str,
) -> MCPKnowledgeGraphsService:
    """Construct MCPKnowledgeGraphsService with real collaborators.

    Uses ``_ManagementKnowledgeGraphRepository`` from the composition layer —
    the same class used in production by ``get_accessible_knowledge_graphs_for_mcp``.
    This keeps the test faithful to the live code path.
    """
    from infrastructure.mcp_dependencies import _ManagementKnowledgeGraphRepository

    kg_repo = _ManagementKnowledgeGraphRepository(session=session)
    return MCPKnowledgeGraphsService(
        authz=spicedb,
        kg_repository=kg_repo,
        user_id=user_id,
        tenant_id=tenant_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAccessibleKnowledgeGraphsListsPermittedKGs:
    """Spec: List accessible knowledge graphs.

    GIVEN an authenticated MCP client with ``view`` permission on KG-1
          (but NOT KG-2)
    WHEN the client reads the ``knowledge-graphs://accessible`` resource
    THEN the response contains KG-1 with id, name, and description
    AND KG-2 is absent from the list
    """

    @pytest.mark.asyncio
    async def test_returns_only_permitted_knowledge_graph(
        self,
        spicedb: AuthorizationProvider,
        async_session: AsyncSession,
        test_user_id: str,
        test_tenant_id: str,
        kg1_id: str,
        kg2_id: str,
        cleanup_kg1_view: None,  # noqa: F811 – fixture for teardown
    ) -> None:
        """KG-1 (with view grant) appears; KG-2 (no grant) is absent.

        Steps:
        1. Grant SpiceDB viewer relationship on KG-1 for test_user_id.
        2. Do NOT grant any relationship on KG-2.
        3. Call get_accessible() and assert exactly KG-1 is returned.

        Spec requirement:
          "the response contains all knowledge graphs the caller has `view`
           permission on within their tenant"
          "knowledge graphs the caller cannot access are omitted entirely"
        """
        # 1. Grant view (viewer) on KG-1 in SpiceDB
        await spicedb.write_relationship(
            resource=format_resource(ResourceType.KNOWLEDGE_GRAPH, kg1_id),
            relation="viewer",
            subject=format_subject(ResourceType.USER, test_user_id),
        )

        # 2. Build service with real collaborators and call get_accessible()
        service = _make_service(spicedb, async_session, test_user_id, test_tenant_id)
        result: list[AccessibleKnowledgeGraph] = await service.get_accessible()

        # 3. Assert exactly one result: KG-1
        result_ids = {kg.id for kg in result}
        assert kg1_id in result_ids, (
            f"KG-1 ({kg1_id}) should be in accessible KGs but was absent. "
            f"Result IDs: {result_ids}"
        )
        assert kg2_id not in result_ids, (
            f"KG-2 ({kg2_id}) should NOT be in accessible KGs (no view grant) "
            f"but was present. Result IDs: {result_ids}"
        )

    @pytest.mark.asyncio
    async def test_each_entry_contains_id_name_description(
        self,
        spicedb: AuthorizationProvider,
        async_session: AsyncSession,
        test_user_id: str,
        test_tenant_id: str,
        kg1_id: str,
        kg2_id: str,
        cleanup_kg1_view: None,
    ) -> None:
        """Each accessible KG entry MUST include id, name, and description.

        Spec: "each entry includes the knowledge graph id, name, and description"
        """
        # Grant view on KG-1
        await spicedb.write_relationship(
            resource=format_resource(ResourceType.KNOWLEDGE_GRAPH, kg1_id),
            relation="viewer",
            subject=format_subject(ResourceType.USER, test_user_id),
        )

        service = _make_service(spicedb, async_session, test_user_id, test_tenant_id)
        result = await service.get_accessible()

        assert len(result) >= 1, "Expected at least one accessible KG (KG-1)"

        kg1 = next((kg for kg in result if kg.id == kg1_id), None)
        assert kg1 is not None, f"KG-1 ({kg1_id}) not found in result"

        # All three required fields must be present and non-empty
        assert kg1.id == kg1_id, "id must match the created KG's ID"
        assert kg1.name == "KG One", f"name mismatch: {kg1.name!r}"
        assert kg1.description == "First test knowledge graph", (
            f"description mismatch: {kg1.description!r}"
        )


class TestAccessibleKnowledgeGraphsReturnsEmptyListWhenNoAccess:
    """Spec: No accessible knowledge graphs.

    GIVEN an authenticated MCP client with NO accessible knowledge graphs
    WHEN the client reads the ``knowledge-graphs://accessible`` resource
    THEN an empty list is returned (not an error)
    """

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_spicedb_grant(
        self,
        spicedb: AuthorizationProvider,
        async_session: AsyncSession,
        test_user_id: str,
        test_tenant_id: str,
        kg1_id: str,
    ) -> None:
        """No SpiceDB grants → empty list returned.

        The user has NO view relationship on any KG. SpiceDB returns an
        empty ID list. The service MUST return ``[]`` (not raise or return
        a partial list).

        Spec: "THEN an empty list is returned"
        This also validates the MCPKnowledgeGraphsService short-circuit path:
        if SpiceDB returns no IDs the DB query is skipped entirely.
        """
        # No SpiceDB relationships written for test_user_id + kg1_id
        service = _make_service(spicedb, async_session, test_user_id, test_tenant_id)
        result: list[AccessibleKnowledgeGraph] = await service.get_accessible()

        assert result == [], (
            f"Expected empty list when caller has no view grants, but got: {result}"
        )

    @pytest.mark.asyncio
    async def test_result_is_list_not_none_or_error(
        self,
        spicedb: AuthorizationProvider,
        async_session: AsyncSession,
        test_user_id: str,
        test_tenant_id: str,
        kg1_id: str,
    ) -> None:
        """Result must be a list (even when empty), not None or an exception.

        Spec: "Then an empty list is returned" — the resource must behave
        identically to a successful call; it is not an error condition.
        """
        service = _make_service(spicedb, async_session, test_user_id, test_tenant_id)
        result = await service.get_accessible()

        assert isinstance(result, list), (
            f"get_accessible() must return a list, got: {type(result).__name__}"
        )
        assert len(result) == 0, (
            f"Expected 0 results for user with no grants, got {len(result)}"
        )
