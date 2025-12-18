"""Graph query service for read operations.

Application service for querying the graph. This service provides
use-case-oriented methods for querying the graph.
"""

from __future__ import annotations

from graph.ports.protocols import NodeNeighborsResult
from graph.application.observability import (
    DefaultGraphServiceProbe,
    GraphServiceProbe,
)
from graph.domain.value_objects import (
    NodeRecord,
    QueryResultRow,
)
from graph.ports.repositories import IGraphReadOnlyRepository


class GraphQueryService:
    """Application service for graph query operations.

    This service provides use-case-oriented methods for querying
    the graph. It wraps the repository with application-level
    concerns like observability and input validation.
    """

    def __init__(
        self,
        repository: IGraphReadOnlyRepository,
        probe: GraphServiceProbe | None = None,
    ):
        """Initialize the service.

        Args:
            repository: The graph repository for data access.
            probe: Optional domain probe for observability.
        """
        self._repository = repository
        self._probe = probe or DefaultGraphServiceProbe()

    def search_by_slug(
        self,
        slug: str,
        node_type: str | None = None,
    ) -> list[NodeRecord]:
        """Search for nodes by their slug.

        Args:
            slug: The entity slug to search for.
            node_type: Optional type filter.

        Returns:
            List of matching nodes.
        """
        nodes = self._repository.find_nodes_by_slug(slug, node_type=node_type)
        self._probe.slug_searched(
            slug=slug,
            node_type=node_type,
            result_count=len(nodes),
        )
        return nodes

    def get_neighbors(
        self,
        node_id: str,
    ) -> NodeNeighborsResult:
        """Get neighboring nodes and connecting edges.

        Args:
            node_id: The ID of the center node.

        Returns:
            NodeNeighborsResult
        """
        return self._repository.get_neighbors(node_id)

    def generate_entity_id(
        self,
        entity_type: str,
        entity_slug: str,
    ) -> str:
        """Generate a deterministic ID for an entity.

        Args:
            entity_type: The type of entity.
            entity_slug: The entity's slug.

        Returns:
            A deterministic ID string.
        """
        return self._repository.generate_id(entity_type, entity_slug)

    def execute_exploration_query(
        self,
        query: str,
    ) -> list[QueryResultRow]:
        """Execute a raw exploration query.

        This method is intended for the Extraction agent to explore
        the graph beyond the fast-path methods. Safeguards are enforced
        by the repository.

        Args:
            query: A Cypher query string.

        Returns:
            List of result dictionaries.
        """
        results = self._repository.execute_raw_query(query)
        self._probe.raw_query_executed(query=query, result_count=len(results))
        return results
