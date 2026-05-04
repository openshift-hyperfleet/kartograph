"""Application service for accessible knowledge graph listing.

Satisfies the ``knowledge_graphs://accessible`` MCP resource requirement:
  - Given an authenticated MCP client
  - When the client reads the resource
  - Then the response contains all KGs the caller has ``view`` permission on

Architecture:
    This service lives in the Query application layer and depends on:
    - AuthorizationProvider (shared_kernel) — to discover accessible KG IDs
    - IAccessibleKnowledgeGraphRepository (query.ports) — to fetch KG metadata

    It does NOT import from management.*, iam.*, or infrastructure.*,
    preserving bounded-context isolation.

Fail-safe:
    Any error from the authorization provider results in an empty list rather
    than an exception, so callers receive a safe (empty) response under failure.
"""

from __future__ import annotations

from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_subject,
)

from query.domain.value_objects import AccessibleKnowledgeGraph
from query.ports.repositories import IAccessibleKnowledgeGraphRepository


class MCPKnowledgeGraphsService:
    """Application service for listing knowledge graphs accessible via MCP.

    Orchestrates a two-step lookup:
    1. SpiceDB ``lookup_resources`` → IDs of KGs the user can VIEW
    2. IAccessibleKnowledgeGraphRepository.find_by_ids_and_tenant → metadata

    Fails safe: any SpiceDB error returns an empty list rather than raising,
    preventing accidental data exposure under auth-system degradation.

    Args:
        authz:         Authorization provider (SpiceDB client or compatible).
        kg_repository: Repository for fetching KG metadata by IDs.
        user_id:       The authenticated user's ID.
        tenant_id:     The user's resolved tenant ID.
    """

    def __init__(
        self,
        authz: AuthorizationProvider,
        kg_repository: IAccessibleKnowledgeGraphRepository,
        user_id: str,
        tenant_id: str,
    ) -> None:
        self._authz = authz
        self._kg_repository = kg_repository
        self._user_id = user_id
        self._tenant_id = tenant_id

    async def get_accessible(self) -> list[AccessibleKnowledgeGraph]:
        """Return all knowledge graphs the user has VIEW permission on.

        Performs:
        1. SpiceDB ``lookup_resources`` for ``knowledge_graph`` with ``view``
        2. Skips DB if no IDs returned (short-circuit)
        3. Fetches metadata, filtered to caller's tenant

        Returns:
            List of AccessibleKnowledgeGraph value objects.
            Empty list if no KGs are accessible or on auth error.
        """
        subject = format_subject(ResourceType.USER, self._user_id)

        try:
            accessible_kg_ids = await self._authz.lookup_resources(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                permission=Permission.VIEW,
                subject=subject,
            )
        except Exception:
            # Fail-safe: any SpiceDB error → no access exposed
            return []

        if not accessible_kg_ids:
            return []

        return await self._kg_repository.find_by_ids_and_tenant(
            ids=accessible_kg_ids,
            tenant_id=self._tenant_id,
        )
