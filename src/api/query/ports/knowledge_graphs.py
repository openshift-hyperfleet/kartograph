"""Knowledge graph port definitions for the Querying bounded context.

Defines the interface contract for listing accessible knowledge graphs
without coupling to the Management bounded context's implementation.
"""

from __future__ import annotations

from typing import Protocol, TypedDict


class AccessibleKnowledgeGraph(TypedDict):
    """A summary of a knowledge graph the caller can access.

    This is the minimal representation needed by MCP clients — just
    enough to identify and describe each accessible knowledge graph.

    Attributes:
        id:          Unique identifier of the knowledge graph.
        name:        Human-readable name of the knowledge graph.
        description: Description of the knowledge graph's content.
    """

    id: str
    name: str
    description: str


class IAccessibleKnowledgeGraphService(Protocol):
    """Port for listing knowledge graphs accessible to a specific user.

    This protocol decouples the Query context from the Management context.
    The concrete implementation (Management's KnowledgeGraphService) is
    wired in the infrastructure composition layer (mcp_dependencies.py).
    """

    async def list_accessible(
        self,
        user_id: str,
        tenant_id: str,
    ) -> list[AccessibleKnowledgeGraph]:
        """Return all knowledge graphs the user has VIEW permission on.

        Args:
            user_id:   The authenticated user's ID.
            tenant_id: The tenant to scope the query to.

        Returns:
            List of knowledge graph summaries (id, name, description).
            Returns an empty list when the user has no accessible KGs.
        """
        ...
