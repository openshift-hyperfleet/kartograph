"""Application services for the Graph bounded context.

Application services orchestrate use cases by coordinating domain
objects and repositories. They are the "front door" to the domain.
"""

from __future__ import annotations

from graph.application.observability import (
    DefaultGraphServiceProbe,
    GraphServiceProbe,
)
from graph.domain.value_objects import EdgeRecord, NodeRecord
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

    def get_nodes_by_path(
        self,
        path: str,
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Get all nodes and edges associated with a source file path.

        Args:
            path: The source file path (e.g., "people/alice.md")

        Returns:
            Tuple of (nodes, edges) found at the path.
        """
        nodes, edges = self._repository.find_nodes_by_path(path)
        self._probe.nodes_queried(
            path=path,
            node_count=len(nodes),
            edge_count=len(edges),
        )
        return nodes, edges

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
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Get neighboring nodes and connecting edges.

        Args:
            node_id: The ID of the center node.

        Returns:
            Tuple of (neighbor_nodes, connecting_edges).
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
    ) -> list[dict]:
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
