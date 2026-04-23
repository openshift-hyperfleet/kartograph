"""Unit tests for GraphSecureEnclaveService.

Tests the per-entity authorization filter that redacts unauthorized
graph entities from query results.

Following TDD — tests written first to define the secure enclave behavior.
Spec reference: specs/iam/authorization.spec.md — "Secure Enclave" requirement.

Key behaviors tested:
- Authorized entities return full properties
- Unauthorized nodes return ID-only (entity removed from topology is NOT allowed)
- Unauthorized edges return ID + start_id + end_id only
- Permission is derived from node/edge knowledge_graph_id property
- Missing, null, or malformed knowledge_graph_id → deny (redact)
- Caching of permission checks per knowledge_graph_id (efficiency)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from graph.application.services.graph_secure_enclave import GraphSecureEnclaveService
from graph.application.services.graph_query_service import GraphQueryService
from graph.domain.value_objects import (
    EdgeRecord,
    NodeRecord,
    RedactedEdgeRecord,
    RedactedNodeRecord,
)
from graph.ports.protocols import NodeNeighborsResult
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_query_service() -> MagicMock:
    """Mock GraphQueryService for synchronous query operations."""
    return MagicMock(spec=GraphQueryService)


@pytest.fixture
def mock_authz() -> AsyncMock:
    """Mock AuthorizationProvider for async permission checks."""
    return AsyncMock(spec=AuthorizationProvider)


@pytest.fixture
def user_id() -> str:
    return "user-alice-123"


@pytest.fixture
def kg_id() -> str:
    return "kg-001"


@pytest.fixture
def alt_kg_id() -> str:
    return "kg-002"


@pytest.fixture
def authorized_node(kg_id: str) -> NodeRecord:
    """A node whose knowledge_graph_id the user can view."""
    return NodeRecord(
        id="person:abc123def456",
        label="person",
        properties={
            "knowledge_graph_id": kg_id,
            "name": "Alice Smith",
            "email": "alice@example.com",
            "slug": "alice-smith",
        },
    )


@pytest.fixture
def unauthorized_node() -> NodeRecord:
    """A node whose knowledge_graph_id the user cannot view."""
    return NodeRecord(
        id="secret:xyz789abc000",
        label="secret",
        properties={
            "knowledge_graph_id": "kg-restricted",
            "classified_info": "top secret",
            "access_level": "classified",
        },
    )


@pytest.fixture
def node_without_kg_id() -> NodeRecord:
    """A node with no knowledge_graph_id property at all."""
    return NodeRecord(
        id="orphan:abc123def456",
        label="orphan",
        properties={
            "name": "Orphan Node",
            "description": "No KG assigned",
        },
    )


@pytest.fixture
def authorized_edge(kg_id: str) -> EdgeRecord:
    """An edge whose knowledge_graph_id the user can view."""
    return EdgeRecord(
        id="knows:abc123def456",
        label="KNOWS",
        start_id="person:alice111111111",
        end_id="person:bob222222222",
        properties={
            "knowledge_graph_id": kg_id,
            "since": "2020",
            "strength": "strong",
        },
    )


@pytest.fixture
def unauthorized_edge() -> EdgeRecord:
    """An edge whose knowledge_graph_id the user cannot view."""
    return EdgeRecord(
        id="secret_rel:xyz789abc000",
        label="SECRET_RELATION",
        start_id="person:alice111111111",
        end_id="secret:xyz789abc000",
        properties={
            "knowledge_graph_id": "kg-restricted",
            "classified": True,
            "level": "top-secret",
        },
    )


@pytest.fixture
def service(
    mock_query_service: MagicMock,
    mock_authz: AsyncMock,
    user_id: str,
) -> GraphSecureEnclaveService:
    """GraphSecureEnclaveService under test with mocked dependencies."""
    return GraphSecureEnclaveService(
        query_service=mock_query_service,
        authz=mock_authz,
        user_id=user_id,
    )


# ---------------------------------------------------------------------------
# Node authorization: Scenario — "Authorized entity — full properties"
# ---------------------------------------------------------------------------


class TestAuthorizedNodeReturnsFullProperties:
    """Spec: Authorized node should return full properties."""

    @pytest.mark.asyncio
    async def test_authorized_node_returns_node_record(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
    ) -> None:
        """An authorized node should be returned as a full NodeRecord."""
        mock_query_service.search_by_slug.return_value = [authorized_node]
        mock_authz.check_permission.return_value = True

        results = await service.search_by_slug("alice-smith")

        assert len(results) == 1
        assert isinstance(results[0], NodeRecord)

    @pytest.mark.asyncio
    async def test_authorized_node_includes_all_properties(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
    ) -> None:
        """An authorized node should include ALL original properties."""
        mock_query_service.search_by_slug.return_value = [authorized_node]
        mock_authz.check_permission.return_value = True

        results = await service.search_by_slug("alice-smith")

        assert isinstance(results[0], NodeRecord)
        assert results[0].properties["name"] == "Alice Smith"
        assert results[0].properties["email"] == "alice@example.com"
        assert (
            results[0].properties["knowledge_graph_id"]
            == authorized_node.properties["knowledge_graph_id"]
        )


# ---------------------------------------------------------------------------
# Node authorization: Scenario — "Unauthorized node — ID-only redaction"
# ---------------------------------------------------------------------------


class TestUnauthorizedNodeReturnsIdOnly:
    """Spec: Unauthorized node should return ID only (redacted)."""

    @pytest.mark.asyncio
    async def test_unauthorized_node_returns_redacted_node_record(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        unauthorized_node: NodeRecord,
    ) -> None:
        """Unauthorized node should be returned as a RedactedNodeRecord."""
        mock_query_service.search_by_slug.return_value = [unauthorized_node]
        mock_authz.check_permission.return_value = False

        results = await service.search_by_slug("secret")

        assert len(results) == 1
        assert isinstance(results[0], RedactedNodeRecord)

    @pytest.mark.asyncio
    async def test_unauthorized_node_preserves_id(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        unauthorized_node: NodeRecord,
    ) -> None:
        """Redacted node must preserve the entity ID for topology preservation."""
        mock_query_service.search_by_slug.return_value = [unauthorized_node]
        mock_authz.check_permission.return_value = False

        results = await service.search_by_slug("secret")

        assert results[0].id == unauthorized_node.id

    @pytest.mark.asyncio
    async def test_unauthorized_node_strips_all_properties(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        unauthorized_node: NodeRecord,
    ) -> None:
        """Redacted node must NOT expose any sensitive properties."""
        mock_query_service.search_by_slug.return_value = [unauthorized_node]
        mock_authz.check_permission.return_value = False

        results = await service.search_by_slug("secret")

        redacted = results[0]
        # RedactedNodeRecord should have no properties field at all
        assert not hasattr(redacted, "properties") or not redacted.properties  # type: ignore[union-attr]
        # Also should not expose label
        assert not hasattr(redacted, "label") or not redacted.label  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_unauthorized_node_not_removed_from_result_set(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        unauthorized_node: NodeRecord,
    ) -> None:
        """Unauthorized nodes must remain in results (graph topology preserved)."""
        mock_query_service.search_by_slug.return_value = [
            authorized_node,
            unauthorized_node,
        ]
        mock_authz.check_permission.side_effect = [True, False]

        results = await service.search_by_slug("test")

        # Both should still be in results (topology preserved)
        assert len(results) == 2
        assert isinstance(results[0], NodeRecord)
        assert isinstance(results[1], RedactedNodeRecord)


# ---------------------------------------------------------------------------
# Node authorization: Scenario — "Missing or unresolvable knowledge_graph_id"
# ---------------------------------------------------------------------------


class TestMissingKnowledgeGraphIdDenied:
    """Spec: Missing/null/malformed knowledge_graph_id must always be denied."""

    @pytest.mark.asyncio
    async def test_node_without_kg_id_is_redacted(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        node_without_kg_id: NodeRecord,
    ) -> None:
        """Node with missing knowledge_graph_id property must be redacted."""
        mock_query_service.search_by_slug.return_value = [node_without_kg_id]

        results = await service.search_by_slug("orphan")

        assert len(results) == 1
        assert isinstance(results[0], RedactedNodeRecord)

    @pytest.mark.asyncio
    async def test_node_without_kg_id_skips_permission_check(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        node_without_kg_id: NodeRecord,
    ) -> None:
        """No permission check should be made when knowledge_graph_id is absent."""
        mock_query_service.search_by_slug.return_value = [node_without_kg_id]

        await service.search_by_slug("orphan")

        # No permission check needed — immediate deny
        mock_authz.check_permission.assert_not_called()

    @pytest.mark.asyncio
    async def test_node_with_null_kg_id_is_redacted(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
    ) -> None:
        """Node with null knowledge_graph_id must be redacted."""
        node = NodeRecord(
            id="node:abc123def456",
            label="test",
            properties={"knowledge_graph_id": None, "name": "Test"},
        )
        mock_query_service.search_by_slug.return_value = [node]

        results = await service.search_by_slug("test")

        assert isinstance(results[0], RedactedNodeRecord)
        mock_authz.check_permission.assert_not_called()

    @pytest.mark.asyncio
    async def test_node_with_non_string_kg_id_is_redacted(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
    ) -> None:
        """Node with non-string knowledge_graph_id (e.g. integer) must be redacted."""
        node = NodeRecord(
            id="node:abc123def456",
            label="test",
            properties={"knowledge_graph_id": 12345, "name": "Test"},
        )
        mock_query_service.search_by_slug.return_value = [node]

        results = await service.search_by_slug("test")

        assert isinstance(results[0], RedactedNodeRecord)
        mock_authz.check_permission.assert_not_called()

    @pytest.mark.asyncio
    async def test_node_with_empty_string_kg_id_is_redacted(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
    ) -> None:
        """Node with empty string knowledge_graph_id must be redacted."""
        node = NodeRecord(
            id="node:abc123def456",
            label="test",
            properties={"knowledge_graph_id": "", "name": "Test"},
        )
        mock_query_service.search_by_slug.return_value = [node]

        results = await service.search_by_slug("test")

        assert isinstance(results[0], RedactedNodeRecord)
        mock_authz.check_permission.assert_not_called()


# ---------------------------------------------------------------------------
# Permission derivation: Scenario — "Permission derivation for graph entities"
# ---------------------------------------------------------------------------


class TestPermissionDerivation:
    """Spec: Permission is derived from knowledge_graph resource via SpiceDB."""

    @pytest.mark.asyncio
    async def test_permission_check_uses_knowledge_graph_resource(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        kg_id: str,
        user_id: str,
    ) -> None:
        """Permission check must target the knowledge_graph resource."""
        mock_query_service.search_by_slug.return_value = [authorized_node]
        mock_authz.check_permission.return_value = True

        await service.search_by_slug("alice-smith")

        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id),
            permission=Permission.VIEW,
            subject=format_subject(ResourceType.USER, user_id),
        )

    @pytest.mark.asyncio
    async def test_permission_check_uses_view_permission(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
    ) -> None:
        """Permission check must use VIEW permission (not edit or manage)."""
        mock_query_service.search_by_slug.return_value = [authorized_node]
        mock_authz.check_permission.return_value = True

        await service.search_by_slug("alice-smith")

        call_kwargs = mock_authz.check_permission.call_args
        assert call_kwargs.kwargs["permission"] == Permission.VIEW

    @pytest.mark.asyncio
    async def test_permission_check_uses_current_user_as_subject(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        user_id: str,
    ) -> None:
        """Permission check must use the requesting user as subject."""
        mock_query_service.search_by_slug.return_value = [authorized_node]
        mock_authz.check_permission.return_value = True

        await service.search_by_slug("alice-smith")

        call_kwargs = mock_authz.check_permission.call_args
        assert call_kwargs.kwargs["subject"] == format_subject(
            ResourceType.USER, user_id
        )


# ---------------------------------------------------------------------------
# Efficiency: Permission result caching per knowledge_graph_id
# ---------------------------------------------------------------------------


class TestPermissionCaching:
    """Efficiency: Repeated checks for same KG should only make one SpiceDB call."""

    @pytest.mark.asyncio
    async def test_multiple_nodes_same_kg_single_permission_check(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        kg_id: str,
    ) -> None:
        """Multiple entities from same KG should require only one permission check."""
        node1 = NodeRecord(
            id="person:aaa111bbb222",
            label="person",
            properties={"knowledge_graph_id": kg_id, "name": "Alice"},
        )
        node2 = NodeRecord(
            id="person:ccc333ddd444",
            label="person",
            properties={"knowledge_graph_id": kg_id, "name": "Bob"},
        )
        node3 = NodeRecord(
            id="person:eee555fff666",
            label="person",
            properties={"knowledge_graph_id": kg_id, "name": "Charlie"},
        )
        mock_query_service.search_by_slug.return_value = [node1, node2, node3]
        mock_authz.check_permission.return_value = True

        results = await service.search_by_slug("test")

        # Three authorized nodes, but only ONE permission check (cached)
        assert len(results) == 3
        assert all(isinstance(r, NodeRecord) for r in results)
        mock_authz.check_permission.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_kg_ids_get_separate_permission_checks(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        kg_id: str,
        alt_kg_id: str,
    ) -> None:
        """Entities from different KGs require separate permission checks."""
        node1 = NodeRecord(
            id="person:aaa111bbb222",
            label="person",
            properties={"knowledge_graph_id": kg_id, "name": "Alice"},
        )
        node2 = NodeRecord(
            id="repo:abc123def456",
            label="repository",
            properties={"knowledge_graph_id": alt_kg_id, "name": "my-repo"},
        )
        mock_query_service.search_by_slug.return_value = [node1, node2]
        mock_authz.check_permission.return_value = True

        await service.search_by_slug("test")

        # Two different KGs → two separate permission checks
        assert mock_authz.check_permission.call_count == 2


# ---------------------------------------------------------------------------
# Edge authorization: Scenario — "Authorized edge — full properties"
# ---------------------------------------------------------------------------


class TestAuthorizedEdgeReturnsFullProperties:
    """Spec: Authorized edge should return full properties."""

    @pytest.mark.asyncio
    async def test_authorized_edge_returns_edge_record(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        authorized_edge: EdgeRecord,
        kg_id: str,
    ) -> None:
        """Authorized edge should be returned as a full EdgeRecord."""
        neighbor = NodeRecord(
            id="person:bob111222333",
            label="person",
            properties={"knowledge_graph_id": kg_id, "name": "Bob"},
        )
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[neighbor],
            edges=[authorized_edge],
        )
        mock_query_service.get_neighbors.return_value = result
        mock_authz.check_permission.return_value = True

        authorized_result = await service.get_neighbors("person:abc123def456")

        assert len(authorized_result.edges) == 1
        assert isinstance(authorized_result.edges[0], EdgeRecord)

    @pytest.mark.asyncio
    async def test_authorized_edge_includes_all_properties(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        authorized_edge: EdgeRecord,
    ) -> None:
        """Authorized edge should include ALL original properties."""
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[],
            edges=[authorized_edge],
        )
        mock_query_service.get_neighbors.return_value = result
        mock_authz.check_permission.return_value = True

        authorized_result = await service.get_neighbors("person:abc123def456")

        edge = authorized_result.edges[0]
        assert isinstance(edge, EdgeRecord)
        assert edge.properties["since"] == "2020"
        assert edge.properties["strength"] == "strong"


# ---------------------------------------------------------------------------
# Edge authorization: Scenario — "Unauthorized edge — endpoint-preserving redaction"
# ---------------------------------------------------------------------------


class TestUnauthorizedEdgeEndpointPreservingRedaction:
    """Spec: Unauthorized edge should return ID, start_id, end_id only."""

    @pytest.mark.asyncio
    async def test_unauthorized_edge_returns_redacted_edge_record(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        unauthorized_edge: EdgeRecord,
        kg_id: str,
    ) -> None:
        """Unauthorized edge should be returned as a RedactedEdgeRecord."""
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[],
            edges=[unauthorized_edge],
        )
        # Central node is authorized, but the unauthorized edge KG is restricted
        mock_authz.check_permission.side_effect = (
            lambda resource, permission, subject: "kg-restricted" not in resource
        )
        mock_query_service.get_neighbors.return_value = result

        authorized_result = await service.get_neighbors("person:abc123def456")

        assert len(authorized_result.edges) == 1
        assert isinstance(authorized_result.edges[0], RedactedEdgeRecord)

    @pytest.mark.asyncio
    async def test_unauthorized_edge_preserves_id(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        unauthorized_edge: EdgeRecord,
    ) -> None:
        """Redacted edge must preserve edge ID."""
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[],
            edges=[unauthorized_edge],
        )
        mock_authz.check_permission.side_effect = (
            lambda resource, permission, subject: "kg-restricted" not in resource
        )
        mock_query_service.get_neighbors.return_value = result

        authorized_result = await service.get_neighbors("person:abc123def456")

        redacted = authorized_result.edges[0]
        assert isinstance(redacted, RedactedEdgeRecord)
        assert redacted.id == unauthorized_edge.id

    @pytest.mark.asyncio
    async def test_unauthorized_edge_preserves_start_id(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        unauthorized_edge: EdgeRecord,
    ) -> None:
        """Redacted edge must preserve start_id (endpoint preservation)."""
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[],
            edges=[unauthorized_edge],
        )
        mock_authz.check_permission.side_effect = (
            lambda resource, permission, subject: "kg-restricted" not in resource
        )
        mock_query_service.get_neighbors.return_value = result

        authorized_result = await service.get_neighbors("person:abc123def456")

        redacted = authorized_result.edges[0]
        assert isinstance(redacted, RedactedEdgeRecord)
        assert redacted.start_id == unauthorized_edge.start_id

    @pytest.mark.asyncio
    async def test_unauthorized_edge_preserves_end_id(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        unauthorized_edge: EdgeRecord,
    ) -> None:
        """Redacted edge must preserve end_id (endpoint preservation)."""
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[],
            edges=[unauthorized_edge],
        )
        mock_authz.check_permission.side_effect = (
            lambda resource, permission, subject: "kg-restricted" not in resource
        )
        mock_query_service.get_neighbors.return_value = result

        authorized_result = await service.get_neighbors("person:abc123def456")

        redacted = authorized_result.edges[0]
        assert isinstance(redacted, RedactedEdgeRecord)
        assert redacted.end_id == unauthorized_edge.end_id

    @pytest.mark.asyncio
    async def test_unauthorized_edge_strips_all_other_properties(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        unauthorized_edge: EdgeRecord,
    ) -> None:
        """Redacted edge must NOT expose edge properties."""
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[],
            edges=[unauthorized_edge],
        )
        mock_authz.check_permission.side_effect = (
            lambda resource, permission, subject: "kg-restricted" not in resource
        )
        mock_query_service.get_neighbors.return_value = result

        authorized_result = await service.get_neighbors("person:abc123def456")

        redacted = authorized_result.edges[0]
        assert isinstance(redacted, RedactedEdgeRecord)
        # RedactedEdgeRecord should have no properties field
        assert not hasattr(redacted, "properties") or not redacted.properties  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_unauthorized_edge_not_removed_from_result_set(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
        authorized_edge: EdgeRecord,
        unauthorized_edge: EdgeRecord,
        kg_id: str,
    ) -> None:
        """Unauthorized edges must remain in results (graph topology preserved)."""
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[],
            edges=[authorized_edge, unauthorized_edge],
        )
        mock_authz.check_permission.side_effect = (
            lambda resource, permission, subject: "kg-restricted" not in resource
        )
        mock_query_service.get_neighbors.return_value = result

        authorized_result = await service.get_neighbors("person:abc123def456")

        # Both edges still present
        assert len(authorized_result.edges) == 2
        assert isinstance(authorized_result.edges[0], EdgeRecord)
        assert isinstance(authorized_result.edges[1], RedactedEdgeRecord)


# ---------------------------------------------------------------------------
# get_neighbors: Central node authorization
# ---------------------------------------------------------------------------


class TestGetNeighborsCentralNodeAuthorization:
    """Test that the central node in get_neighbors is also authorized."""

    @pytest.mark.asyncio
    async def test_authorized_central_node_returns_node_record(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        authorized_node: NodeRecord,
    ) -> None:
        """Authorized central node should be returned as NodeRecord."""
        result = NodeNeighborsResult(
            central_node=authorized_node,
            nodes=[],
            edges=[],
        )
        mock_query_service.get_neighbors.return_value = result
        mock_authz.check_permission.return_value = True

        authorized_result = await service.get_neighbors("person:abc123def456")

        assert isinstance(authorized_result.central_node, NodeRecord)
        assert authorized_result.central_node.id == authorized_node.id

    @pytest.mark.asyncio
    async def test_unauthorized_central_node_returns_redacted_node_record(
        self,
        service: GraphSecureEnclaveService,
        mock_query_service: MagicMock,
        mock_authz: AsyncMock,
        unauthorized_node: NodeRecord,
    ) -> None:
        """Unauthorized central node should be returned as RedactedNodeRecord."""
        result = NodeNeighborsResult(
            central_node=unauthorized_node,
            nodes=[],
            edges=[],
        )
        mock_query_service.get_neighbors.return_value = result
        mock_authz.check_permission.return_value = False

        authorized_result = await service.get_neighbors("secret:xyz789abc000")

        assert isinstance(authorized_result.central_node, RedactedNodeRecord)
        assert authorized_result.central_node.id == unauthorized_node.id
