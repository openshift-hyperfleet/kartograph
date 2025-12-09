"""Repository interfaces (ports) for the Graph bounded context.

These protocols define the contracts that repositories must implement.
The Extraction context depends on these interfaces, while the Graph
context provides the concrete implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from graph.domain.value_objects import EdgeRecord, NodeRecord, QueryResultRow


@runtime_checkable
class IGraphReadOnlyRepository(Protocol):
    """Read-only repository interface for graph queries.

    This interface is designed for the Extraction context to query
    the existing graph state. Implementations are scoped to a specific
    data_source_id upon instantiation for security isolation.

    The interface provides both "fast path" methods (optimized queries)
    and an "exploration path" (raw query execution with safeguards).
    """

    # --- Fast Path Methods ---

    def find_nodes_by_path(
        self,
        path: str,
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Find nodes and their edges by source file path.

        Args:
            path: The source file path (e.g., "people/alice.md")

        Returns:
            Tuple of (nodes, edges) associated with the path.
        """
        ...

    def find_nodes_by_slug(
        self,
        slug: str,
        node_type: str | None = None,
    ) -> list[NodeRecord]:
        """Find nodes by their slug, optionally filtered by type.

        Args:
            slug: The entity slug (e.g., "alice-smith")
            node_type: Optional type filter (e.g., "Person")

        Returns:
            List of matching nodes.
        """
        ...

    def get_neighbors(
        self,
        node_id: str,
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Get all neighboring nodes and connecting edges.

        Args:
            node_id: The ID of the center node.

        Returns:
            Tuple of (neighbor_nodes, connecting_edges).
        """
        ...

    # --- Idempotency Method ---

    def generate_id(
        self,
        entity_type: str,
        entity_slug: str,
    ) -> str:
        """Generate a deterministic ID for an entity.

        This method combines the repository's scoped data_source_id
        with the entity type and slug to produce a stable, reproducible
        identifier. Essential for idempotent mutation operations.

        Args:
            entity_type: The type of entity (e.g., "person", "repository")
            entity_slug: The entity's slug (e.g., "alice-smith")

        Returns:
            A deterministic ID string (e.g., "person:abc123def")
        """
        ...

    # --- Exploration Method ---

    def execute_raw_query(
        self,
        query: str,
    ) -> list[QueryResultRow]:
        """Execute a raw Cypher query with safeguards.

        This method allows the Extraction agent to explore the graph
        beyond the fast-path methods. Implementations MUST enforce:
        - Read-only operations only
        - Result limits (e.g., max 100 rows)
        - Query timeout (e.g., 5 seconds)
        - Scope to the repository's data_source_id

        Args:
            query: A Cypher query string.

        Returns:
            List of result dictionaries.

        Raises:
            GraphQueryError: If the query fails or violates safeguards.
        """
        ...
