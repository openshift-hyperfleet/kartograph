"""Unit tests for the knowledge_graphs://accessible MCP resource.

Covers spec: Requirement: Knowledge Graphs Resource (mcp-server.spec.md)

Scenarios:
- List accessible knowledge graphs: returns id, name, description for each accessible KG
- No accessible knowledge graphs: returns empty list
- Inaccessible KGs are omitted entirely from the response
"""

from __future__ import annotations

from typing import Any

import pytest

from query.application.kg_service import MCPKnowledgeGraphsService
from query.domain.value_objects import AccessibleKnowledgeGraph


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeAuthorizationProvider:
    """Fake AuthorizationProvider for testing KG lookup.

    Returns the pre-configured list of accessible KG IDs.
    If ``raise_error`` is True, raises on lookup_resources.
    """

    def __init__(
        self,
        accessible_kg_ids: list[str] | None = None,
        raise_error: bool = False,
    ) -> None:
        self.accessible_kg_ids = accessible_kg_ids or []
        self.raise_error = raise_error
        self.lookup_calls: list[dict[str, str]] = []

    async def lookup_resources(
        self,
        resource_type: str,
        permission: str,
        subject: str,
    ) -> list[str]:
        self.lookup_calls.append(
            {
                "resource_type": resource_type,
                "permission": permission,
                "subject": subject,
            }
        )
        if self.raise_error:
            raise Exception("SpiceDB unavailable")
        return self.accessible_kg_ids

    # Required protocol stubs (no-ops)
    async def check_permission(
        self, resource: str, permission: str, subject: str
    ) -> bool:
        return False

    async def bulk_check_permission(self, requests: list) -> set[str]:
        return set()

    async def write_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def write_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def delete_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationships_by_filter(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        pass

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
        optional_subject_relation: str | None = None,
    ) -> list:
        return []

    async def read_relationships(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list:
        return []


class FakeAccessibleKnowledgeGraphRepository:
    """In-memory fake for IAccessibleKnowledgeGraphRepository.

    Returns pre-configured KG entries filtered by IDs and tenant_id.
    """

    def __init__(self, kgs: list[AccessibleKnowledgeGraph] | None = None) -> None:
        self._kgs = kgs or []
        self.find_calls: list[dict[str, Any]] = []

    def seed(self, *kgs: AccessibleKnowledgeGraph) -> None:
        """Pre-populate the store."""
        self._kgs = list(kgs)

    async def find_by_ids_and_tenant(
        self,
        ids: list[str],
        tenant_id: str,
    ) -> list[AccessibleKnowledgeGraph]:
        self.find_calls.append({"ids": ids, "tenant_id": tenant_id})
        return [kg for kg in self._kgs if kg.id in ids and kg.tenant_id == tenant_id]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def authz_with_kgs() -> FakeAuthorizationProvider:
    """Authorization provider that grants access to kg-1 and kg-2."""
    return FakeAuthorizationProvider(accessible_kg_ids=["kg-1", "kg-2"])


@pytest.fixture
def authz_empty() -> FakeAuthorizationProvider:
    """Authorization provider that grants no access."""
    return FakeAuthorizationProvider(accessible_kg_ids=[])


@pytest.fixture
def kg_repo() -> FakeAccessibleKnowledgeGraphRepository:
    """Repository with two knowledge graphs in tenant-a."""
    repo = FakeAccessibleKnowledgeGraphRepository()
    repo.seed(
        AccessibleKnowledgeGraph(
            id="kg-1",
            tenant_id="tenant-a",
            name="Graph One",
            description="First knowledge graph",
        ),
        AccessibleKnowledgeGraph(
            id="kg-2",
            tenant_id="tenant-a",
            name="Graph Two",
            description="Second knowledge graph",
        ),
    )
    return repo


# ---------------------------------------------------------------------------
# Tests: MCPKnowledgeGraphsService
# ---------------------------------------------------------------------------


class TestMCPKnowledgeGraphsServiceInit:
    """Tests for MCPKnowledgeGraphsService initialization."""

    def test_stores_user_id(self, authz_with_kgs, kg_repo) -> None:
        """Service should store the user_id."""
        service = MCPKnowledgeGraphsService(
            authz=authz_with_kgs,
            kg_repository=kg_repo,
            user_id="user-xyz",
            tenant_id="tenant-a",
        )
        assert service._user_id == "user-xyz"

    def test_stores_tenant_id(self, authz_with_kgs, kg_repo) -> None:
        """Service should store the tenant_id."""
        service = MCPKnowledgeGraphsService(
            authz=authz_with_kgs,
            kg_repository=kg_repo,
            user_id="user-xyz",
            tenant_id="tenant-a",
        )
        assert service._tenant_id == "tenant-a"


class TestGetAccessible:
    """Tests for MCPKnowledgeGraphsService.get_accessible."""

    @pytest.mark.asyncio
    async def test_returns_accessible_kgs(self, authz_with_kgs, kg_repo) -> None:
        """Returns KGs the user has view permission on."""
        service = MCPKnowledgeGraphsService(
            authz=authz_with_kgs,
            kg_repository=kg_repo,
            user_id="user-alice",
            tenant_id="tenant-a",
        )
        result = await service.get_accessible()

        assert len(result) == 2
        ids = {kg.id for kg in result}
        assert ids == {"kg-1", "kg-2"}

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_accessible(
        self, authz_empty, kg_repo
    ) -> None:
        """Returns empty list when SpiceDB grants no access.

        Spec: No accessible knowledge graphs scenario.
        """
        service = MCPKnowledgeGraphsService(
            authz=authz_empty,
            kg_repository=kg_repo,
            user_id="user-alice",
            tenant_id="tenant-a",
        )
        result = await service.get_accessible()

        assert result == []

    @pytest.mark.asyncio
    async def test_skips_db_query_when_no_spicedb_ids(
        self, authz_empty, kg_repo
    ) -> None:
        """Should not query the DB if SpiceDB returns no accessible IDs."""
        service = MCPKnowledgeGraphsService(
            authz=authz_empty,
            kg_repository=kg_repo,
            user_id="user-alice",
            tenant_id="tenant-a",
        )
        await service.get_accessible()

        # DB should not be queried — short-circuit on empty SpiceDB result
        assert kg_repo.find_calls == []

    @pytest.mark.asyncio
    async def test_result_includes_id_name_description(
        self, authz_with_kgs, kg_repo
    ) -> None:
        """Each accessible KG should include id, name, and description."""
        service = MCPKnowledgeGraphsService(
            authz=authz_with_kgs,
            kg_repository=kg_repo,
            user_id="user-alice",
            tenant_id="tenant-a",
        )
        result = await service.get_accessible()

        # Sort by id for determinism
        sorted_result = sorted(result, key=lambda kg: kg.id)
        assert sorted_result[0].id == "kg-1"
        assert sorted_result[0].name == "Graph One"
        assert sorted_result[0].description == "First knowledge graph"

    @pytest.mark.asyncio
    async def test_uses_correct_user_subject_in_spicedb_call(
        self, authz_with_kgs, kg_repo
    ) -> None:
        """SpiceDB lookup should use the user:user_id subject format."""
        service = MCPKnowledgeGraphsService(
            authz=authz_with_kgs,
            kg_repository=kg_repo,
            user_id="user-alice",
            tenant_id="tenant-a",
        )
        await service.get_accessible()

        assert len(authz_with_kgs.lookup_calls) == 1
        call = authz_with_kgs.lookup_calls[0]
        assert "user-alice" in call["subject"]

    @pytest.mark.asyncio
    async def test_queries_knowledge_graph_resource_type(
        self, authz_with_kgs, kg_repo
    ) -> None:
        """SpiceDB lookup should use knowledge_graph resource type."""
        service = MCPKnowledgeGraphsService(
            authz=authz_with_kgs,
            kg_repository=kg_repo,
            user_id="user-alice",
            tenant_id="tenant-a",
        )
        await service.get_accessible()

        call = authz_with_kgs.lookup_calls[0]
        assert call["resource_type"] == "knowledge_graph"

    @pytest.mark.asyncio
    async def test_queries_view_permission(self, authz_with_kgs, kg_repo) -> None:
        """SpiceDB lookup should check view permission."""
        service = MCPKnowledgeGraphsService(
            authz=authz_with_kgs,
            kg_repository=kg_repo,
            user_id="user-alice",
            tenant_id="tenant-a",
        )
        await service.get_accessible()

        call = authz_with_kgs.lookup_calls[0]
        assert call["permission"] == "view"

    @pytest.mark.asyncio
    async def test_filters_kgs_by_tenant(self) -> None:
        """KGs from a different tenant should not appear.

        SpiceDB may return KG IDs that belong to a different tenant
        if the data is inconsistent. The DB query should filter by tenant_id.
        """
        # Only grant access to kg-other-tenant which is in a different tenant
        authz = FakeAuthorizationProvider(accessible_kg_ids=["kg-other-tenant"])
        repo = FakeAccessibleKnowledgeGraphRepository()
        repo.seed(
            AccessibleKnowledgeGraph(
                id="kg-other-tenant",
                tenant_id="other-tenant",
                name="Other Tenant Graph",
                description="Should not appear",
            )
        )

        service = MCPKnowledgeGraphsService(
            authz=authz,
            kg_repository=repo,
            user_id="user-alice",
            tenant_id="my-tenant",  # Different tenant
        )
        result = await service.get_accessible()

        # Should return empty because no KGs match "my-tenant"
        assert result == []

    @pytest.mark.asyncio
    async def test_spicedb_error_returns_empty_list(self) -> None:
        """SpiceDB errors should result in empty list (fail-safe).

        Spec: Authentication service unavailable → graceful degradation.
        """
        authz = FakeAuthorizationProvider(raise_error=True)
        repo = FakeAccessibleKnowledgeGraphRepository()

        service = MCPKnowledgeGraphsService(
            authz=authz,
            kg_repository=repo,
            user_id="user-alice",
            tenant_id="tenant-a",
        )
        result = await service.get_accessible()

        assert result == []


# ---------------------------------------------------------------------------
# Tests: AccessibleKnowledgeGraph value object
# ---------------------------------------------------------------------------


class TestAccessibleKnowledgeGraph:
    """Tests for the AccessibleKnowledgeGraph value object."""

    def test_stores_id_name_description(self) -> None:
        """Value object should store id, name, description."""
        kg = AccessibleKnowledgeGraph(
            id="kg-1",
            tenant_id="tenant-a",
            name="My Graph",
            description="A test graph",
        )
        assert kg.id == "kg-1"
        assert kg.tenant_id == "tenant-a"
        assert kg.name == "My Graph"
        assert kg.description == "A test graph"

    def test_is_immutable(self) -> None:
        """Value object should be immutable."""
        kg = AccessibleKnowledgeGraph(
            id="kg-1",
            tenant_id="tenant-a",
            name="My Graph",
            description="",
        )
        with pytest.raises(Exception):
            kg.id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: MCP resource registration
# ---------------------------------------------------------------------------


class TestKnowledgeGraphsResourceRegistration:
    """Tests that the MCP resource is correctly registered.

    Verifies the resource exists in the MCP app with the correct URI.

    Note: The spec uses ``knowledge_graphs://accessible`` but RFC 3986 disallows
    underscores in URL schemes. We register as ``knowledge-graphs://accessible``
    (hyphen) which FastMCP's AnyUrl validator accepts. MCP clients discover the
    actual URI via ``resources/list``.
    """

    def test_knowledge_graphs_resource_registered(self) -> None:
        """The knowledge-graphs://accessible resource should be registered in the MCP server.

        Spec: The system SHALL expose the caller's accessible knowledge graphs
        as an MCP resource. We use a hyphen in the URI scheme (technically
        required; underscore is invalid per RFC 3986).
        """
        from query.presentation.mcp import mcp

        # Get all registered resources from the FastMCP instance
        resources = mcp._resource_manager._resources

        resource_uris = {str(uri) for uri in resources.keys()}

        assert "knowledge-graphs://accessible" in resource_uris, (
            f"Expected 'knowledge-graphs://accessible' in MCP resources, "
            f"but got: {resource_uris}"
        )

    def test_instructions_resource_still_registered(self) -> None:
        """The instructions://agent resource should still be present (regression guard)."""
        from query.presentation.mcp import mcp

        resources = mcp._resource_manager._resources
        resource_uris = {str(uri) for uri in resources.keys()}

        assert "instructions://agent" in resource_uris
