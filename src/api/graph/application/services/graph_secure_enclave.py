"""Secure Enclave service for per-entity graph authorization.

Implements the "Secure Enclave — Per-Entity Graph Authorization" requirement
from specs/iam/authorization.spec.md.

The secure enclave filters graph query results based on per-entity authorization,
redacting content that the requesting user is not permitted to view. Graph topology
is always preserved — unauthorized entities remain in the result set but with
their properties stripped according to their type:

- Authorized node: full NodeRecord returned
- Unauthorized node: RedactedNodeRecord (ID only) returned
- Authorized edge: full EdgeRecord returned
- Unauthorized edge: RedactedEdgeRecord (ID, start_id, end_id only) returned

Permission derivation:
    Each node/edge carries a ``knowledge_graph_id`` property. The service
    checks VIEW permission on the corresponding KnowledgeGraph resource via
    SpiceDB. If the property is absent, null, non-string, or empty, access
    is denied immediately without a permission check.

Performance:
    Permission results are cached per ``knowledge_graph_id`` within a single
    request to avoid redundant SpiceDB calls when multiple entities share
    the same parent KnowledgeGraph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence, Union

from graph.application.services.graph_query_service import GraphQueryService
from graph.domain.value_objects import (
    EdgeRecord,
    NodeRecord,
    RedactedEdgeRecord,
    RedactedNodeRecord,
)
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)

AuthorizedNode = Union[NodeRecord, RedactedNodeRecord]
AuthorizedEdge = Union[EdgeRecord, RedactedEdgeRecord]


@dataclass(frozen=True)
class SecureEnclaveNeighborsResult:
    """Container for get_neighbors results after secure enclave authorization.

    Mirrors ``NodeNeighborsResult`` but with union types that allow either
    full or redacted entity records.

    Attributes:
        central_node: The queried node (full or redacted).
        nodes: Neighboring nodes (each full or redacted based on authorization).
        edges: Connecting edges (each full or redacted based on authorization).
    """

    central_node: AuthorizedNode
    nodes: Sequence[AuthorizedNode]
    edges: Sequence[AuthorizedEdge]


class GraphSecureEnclaveService:
    """Application service that applies per-entity authorization to graph results.

    Wraps ``GraphQueryService`` and filters all returned entities through
    the authorization provider, returning redacted records for entities the
    requesting user is not permitted to view.

    This service is the canonical entry point for user-facing graph queries.
    It must be wired into the presentation layer instead of the bare
    ``GraphQueryService`` for any endpoint that returns graph entities to end users.

    Args:
        query_service: The underlying graph query service.
        authz: Authorization provider (SpiceDB client or compatible).
        user_id: The ID of the requesting user (subject for permission checks).
    """

    def __init__(
        self,
        query_service: GraphQueryService,
        authz: AuthorizationProvider,
        user_id: str,
    ) -> None:
        self._query_service = query_service
        self._authz = authz
        self._user_id = user_id
        # Cache: kg_id → bool (True = user has VIEW permission)
        self._kg_permission_cache: dict[str, bool] = {}

    async def search_by_slug(
        self,
        slug: str,
        node_type: str | None = None,
    ) -> list[AuthorizedNode]:
        """Search for nodes by slug with per-entity authorization.

        Args:
            slug: The entity slug to search for.
            node_type: Optional type filter.

        Returns:
            List of NodeRecord (authorized) or RedactedNodeRecord (unauthorized).
            Unauthorized nodes are NOT removed — graph topology is preserved.
        """
        raw_nodes = self._query_service.search_by_slug(slug, node_type=node_type)
        return [await self._authorize_node(node) for node in raw_nodes]

    async def get_neighbors(
        self,
        node_id: str,
    ) -> SecureEnclaveNeighborsResult:
        """Get neighboring nodes and edges with per-entity authorization.

        Args:
            node_id: The ID of the center node.

        Returns:
            SecureEnclaveNeighborsResult with all entities authorized/redacted.
        """
        raw_result = self._query_service.get_neighbors(node_id)

        central_node = await self._authorize_node(raw_result.central_node)
        nodes = [await self._authorize_node(n) for n in raw_result.nodes]
        edges = [await self._authorize_edge(e) for e in raw_result.edges]

        return SecureEnclaveNeighborsResult(
            central_node=central_node,
            nodes=nodes,
            edges=edges,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _authorize_node(self, node: NodeRecord) -> AuthorizedNode:
        """Authorize a single node, returning full record or ID-only redaction."""
        kg_id = self._extract_kg_id(node.properties)
        if kg_id is None:
            # Missing, null, non-string, or empty knowledge_graph_id → deny
            return RedactedNodeRecord(id=node.id)

        if await self._check_kg_view(kg_id):
            return node

        return RedactedNodeRecord(id=node.id)

    async def _authorize_edge(self, edge: EdgeRecord) -> AuthorizedEdge:
        """Authorize a single edge, returning full record or endpoint-only redaction."""
        kg_id = self._extract_kg_id(edge.properties)
        if kg_id is None:
            # Missing, null, non-string, or empty knowledge_graph_id → deny
            return RedactedEdgeRecord(
                id=edge.id,
                start_id=edge.start_id,
                end_id=edge.end_id,
            )

        if await self._check_kg_view(kg_id):
            return edge

        return RedactedEdgeRecord(
            id=edge.id,
            start_id=edge.start_id,
            end_id=edge.end_id,
        )

    async def _check_kg_view(self, kg_id: str) -> bool:
        """Check if the user has VIEW permission on a KnowledgeGraph.

        Results are cached per kg_id to avoid redundant SpiceDB calls
        when multiple entities share the same parent KnowledgeGraph.

        Args:
            kg_id: The KnowledgeGraph resource ID.

        Returns:
            True if the user has VIEW permission, False otherwise.
        """
        if kg_id in self._kg_permission_cache:
            return self._kg_permission_cache[kg_id]

        try:
            has_permission = await self._authz.check_permission(
                resource=format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id),
                permission=Permission.VIEW,
                subject=format_subject(ResourceType.USER, self._user_id),
            )
        except Exception:
            # Any error during permission check → deny (fail safe)
            has_permission = False

        self._kg_permission_cache[kg_id] = has_permission
        return has_permission

    @staticmethod
    def _extract_kg_id(properties: dict[str, Any]) -> str | None:
        """Extract and validate the knowledge_graph_id from entity properties.

        Returns None if the value is absent, None, non-string, or empty —
        all of which trigger immediate denial per the spec.

        Args:
            properties: Entity properties dictionary.

        Returns:
            A non-empty string KG ID, or None if unresolvable.
        """
        kg_id = properties.get("knowledge_graph_id")
        if not kg_id or not isinstance(kg_id, str):
            return None
        return kg_id
