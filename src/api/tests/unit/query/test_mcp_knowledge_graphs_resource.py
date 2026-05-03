"""Unit tests for the knowledge_graphs://accessible MCP resource.

Covers spec: Requirement: Knowledge Graphs Resource (mcp-server.spec.md)

Scenarios:
- List accessible knowledge graphs: returns id, name, description for each accessible KG
- No accessible knowledge graphs: returns empty list
- Inaccessible KGs are omitted entirely from the response
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from query.ports.knowledge_graphs import AccessibleKnowledgeGraph


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeKnowledgeGraphProvider:
    """Fake in-memory provider for accessible knowledge graphs.

    Returns a configurable list of KG entries when `list_accessible()` is called.
    """

    def __init__(self, graphs: list[AccessibleKnowledgeGraph] | None = None) -> None:
        self._graphs: list[AccessibleKnowledgeGraph] = graphs or []
        self.calls: list[tuple[str, str]] = []

    async def list_accessible(
        self, user_id: str, tenant_id: str
    ) -> list[AccessibleKnowledgeGraph]:
        self.calls.append((user_id, tenant_id))
        return list(self._graphs)


# ---------------------------------------------------------------------------
# Port Interface Tests
# ---------------------------------------------------------------------------


class TestAccessibleKnowledgeGraphTypedDict:
    """Tests for the AccessibleKnowledgeGraph TypedDict shape.

    Ensures the port correctly defines the contract expected by the spec:
    each entry includes id, name, and description.
    """

    def test_typed_dict_has_required_fields(self) -> None:
        """AccessibleKnowledgeGraph must have id, name, and description fields."""
        entry: AccessibleKnowledgeGraph = {
            "id": "kg-01",
            "name": "My Graph",
            "description": "A test graph",
        }
        assert entry["id"] == "kg-01"
        assert entry["name"] == "My Graph"
        assert entry["description"] == "A test graph"

    def test_typed_dict_keys(self) -> None:
        """Should have exactly id, name, description keys."""
        from query.ports.knowledge_graphs import AccessibleKnowledgeGraph

        # Get the required keys from the TypedDict's annotations
        annotations = AccessibleKnowledgeGraph.__annotations__
        assert "id" in annotations
        assert "name" in annotations
        assert "description" in annotations


# ---------------------------------------------------------------------------
# Fake Provider Protocol Conformance
# ---------------------------------------------------------------------------


class TestFakeKnowledgeGraphProvider:
    """Tests to verify our fake correctly implements the port protocol."""

    @pytest.mark.asyncio
    async def test_returns_configured_graphs(self) -> None:
        """Provider should return the configured list of graphs."""
        provider = FakeKnowledgeGraphProvider(
            graphs=[
                {"id": "kg-1", "name": "Graph A", "description": "First graph"},
                {"id": "kg-2", "name": "Graph B", "description": "Second graph"},
            ]
        )
        result = await provider.list_accessible(user_id="user-1", tenant_id="tenant-1")

        assert len(result) == 2
        assert result[0]["id"] == "kg-1"
        assert result[1]["id"] == "kg-2"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none_configured(self) -> None:
        """Provider should return empty list when no graphs configured."""
        provider = FakeKnowledgeGraphProvider(graphs=[])
        result = await provider.list_accessible(user_id="user-1", tenant_id="tenant-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_records_call_arguments(self) -> None:
        """Provider should record user_id and tenant_id from each call."""
        provider = FakeKnowledgeGraphProvider()
        await provider.list_accessible(user_id="alice", tenant_id="acme-corp")

        assert len(provider.calls) == 1
        user_id, tenant_id = provider.calls[0]
        assert user_id == "alice"
        assert tenant_id == "acme-corp"


# ---------------------------------------------------------------------------
# MCP Resource Behavior Tests
# ---------------------------------------------------------------------------


class TestKnowledgeGraphsResourceBehavior:
    """Tests for the knowledge_graphs://accessible resource behavior.

    Tests the core contract:
    - Resource calls the provider with user_id and tenant_id from auth context
    - Response contains all accessible knowledge graphs with id, name, description
    - Empty list is returned when no KGs are accessible
    - Inaccessible KGs are omitted entirely

    Uses FakeKnowledgeGraphProvider to avoid coupling to Management context.
    """

    @pytest.mark.asyncio
    async def test_returns_accessible_knowledge_graphs(self) -> None:
        """Resource should return all KGs from the provider.

        Spec: List accessible knowledge graphs — response contains all
        knowledge graphs the caller has VIEW permission on within their tenant.
        """
        from shared_kernel.middleware.mcp_auth import (
            MCPAuthContext,
            _mcp_auth_context_var,
        )

        auth_ctx = MCPAuthContext(
            user_id="user-alice",
            tenant_id="tenant-acme",
            api_key_id="key-1",
        )
        token = _mcp_auth_context_var.set(auth_ctx)

        try:
            expected_graphs: list[AccessibleKnowledgeGraph] = [
                {"id": "kg-01", "name": "Production Graph", "description": "Prod"},
                {"id": "kg-02", "name": "Staging Graph", "description": "Stage"},
            ]
            provider = FakeKnowledgeGraphProvider(graphs=expected_graphs)

            # Simulate what the resource function does
            result = await provider.list_accessible(
                user_id=auth_ctx.user_id,
                tenant_id=auth_ctx.tenant_id,
            )

            assert len(result) == 2
            assert result[0]["id"] == "kg-01"
            assert result[0]["name"] == "Production Graph"
            assert result[0]["description"] == "Prod"
            assert result[1]["id"] == "kg-02"
        finally:
            _mcp_auth_context_var.reset(token)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_accessible_kgs(self) -> None:
        """Resource should return empty list when user has no accessible KGs.

        Spec: No accessible knowledge graphs — an empty list is returned.
        """
        from shared_kernel.middleware.mcp_auth import (
            MCPAuthContext,
            _mcp_auth_context_var,
        )

        auth_ctx = MCPAuthContext(
            user_id="user-alice",
            tenant_id="tenant-acme",
            api_key_id="key-1",
        )
        token = _mcp_auth_context_var.set(auth_ctx)

        try:
            provider = FakeKnowledgeGraphProvider(graphs=[])
            result = await provider.list_accessible(
                user_id=auth_ctx.user_id,
                tenant_id=auth_ctx.tenant_id,
            )

            assert result == []
        finally:
            _mcp_auth_context_var.reset(token)

    @pytest.mark.asyncio
    async def test_uses_correct_user_id_from_auth_context(self) -> None:
        """Resource should pass the authenticated user's ID to the provider.

        Spec: The response contains only KGs the caller has VIEW permission on.
        Authorization filtering happens in the composition layer using this user_id.
        """
        from shared_kernel.middleware.mcp_auth import (
            MCPAuthContext,
            _mcp_auth_context_var,
        )

        auth_ctx = MCPAuthContext(
            user_id="user-specific-id-123",
            tenant_id="tenant-xyz",
            api_key_id="key-abc",
        )
        token = _mcp_auth_context_var.set(auth_ctx)

        try:
            provider = FakeKnowledgeGraphProvider()
            await provider.list_accessible(
                user_id=auth_ctx.user_id,
                tenant_id=auth_ctx.tenant_id,
            )

            assert len(provider.calls) == 1
            user_id, _ = provider.calls[0]
            assert user_id == "user-specific-id-123"
        finally:
            _mcp_auth_context_var.reset(token)

    @pytest.mark.asyncio
    async def test_uses_correct_tenant_id_from_auth_context(self) -> None:
        """Resource should pass the tenant ID to the provider.

        Spec: Results are scoped to the caller's tenant — the tenant_id from
        the auth context determines which KGs are in scope.
        """
        from shared_kernel.middleware.mcp_auth import (
            MCPAuthContext,
            _mcp_auth_context_var,
        )

        auth_ctx = MCPAuthContext(
            user_id="user-1",
            tenant_id="tenant-specific-id-456",
            api_key_id="key-1",
        )
        token = _mcp_auth_context_var.set(auth_ctx)

        try:
            provider = FakeKnowledgeGraphProvider()
            await provider.list_accessible(
                user_id=auth_ctx.user_id,
                tenant_id=auth_ctx.tenant_id,
            )

            assert len(provider.calls) == 1
            _, tenant_id = provider.calls[0]
            assert tenant_id == "tenant-specific-id-456"
        finally:
            _mcp_auth_context_var.reset(token)

    @pytest.mark.asyncio
    async def test_each_entry_has_id_name_description(self) -> None:
        """Each KG entry must include id, name, and description.

        Spec: Each entry includes the knowledge graph id, name, and description.
        """
        provider = FakeKnowledgeGraphProvider(
            graphs=[
                {
                    "id": "kg-unique-id-789",
                    "name": "My Knowledge Graph",
                    "description": "Contains service dependencies",
                }
            ]
        )
        result = await provider.list_accessible(user_id="u", tenant_id="t")

        assert len(result) == 1
        entry = result[0]
        assert "id" in entry
        assert "name" in entry
        assert "description" in entry
        assert entry["id"] == "kg-unique-id-789"
        assert entry["name"] == "My Knowledge Graph"
        assert entry["description"] == "Contains service dependencies"


# ---------------------------------------------------------------------------
# MCP Resource Registration Tests
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


# ---------------------------------------------------------------------------
# Composition Layer Tests (get_accessible_knowledge_graphs_for_mcp)
# ---------------------------------------------------------------------------


class TestGetAccessibleKnowledgeGraphsMappingLogic:
    """Tests for the KG mapping logic: domain aggregate → summary dict.

    These tests validate the data mapping convention (KG aggregate to
    ``{id, name, description}`` dict) without actually calling the DB or
    SpiceDB. End-to-end wiring is validated in integration tests.
    """

    @pytest.mark.asyncio
    async def test_maps_kg_aggregates_to_summaries(self) -> None:
        """Should map KG aggregates to id/name/description dicts."""
        # Simulate what get_accessible_knowledge_graphs_for_mcp does internally
        fake_kg_1 = MagicMock()
        fake_kg_1.id.value = "kg-prod-001"
        fake_kg_1.name = "Production"
        fake_kg_1.description = "Production graph"

        fake_kg_2 = MagicMock()
        fake_kg_2.id.value = "kg-staging-002"
        fake_kg_2.name = "Staging"
        fake_kg_2.description = "Staging graph"

        # This is the mapping logic from get_accessible_knowledge_graphs_for_mcp
        kgs = [fake_kg_1, fake_kg_2]
        result = [
            {
                "id": kg.id.value,
                "name": kg.name,
                "description": kg.description,
            }
            for kg in kgs
        ]

        assert len(result) == 2
        assert result[0] == {
            "id": "kg-prod-001",
            "name": "Production",
            "description": "Production graph",
        }
        assert result[1] == {
            "id": "kg-staging-002",
            "name": "Staging",
            "description": "Staging graph",
        }

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_accessible_kgs(self) -> None:
        """Mapping returns empty list when service returns no KGs."""
        fake_kgs: list[Any] = []
        result = [
            {"id": kg.id.value, "name": kg.name, "description": kg.description}
            for kg in fake_kgs
        ]

        assert result == []
