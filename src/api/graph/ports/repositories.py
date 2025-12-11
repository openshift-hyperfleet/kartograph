"""Repository interfaces (ports) for the Graph bounded context.

These protocols define the contracts that repositories must implement.
The Extraction context depends on these interfaces, while the Graph
context provides the concrete implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from graph.domain.value_objects import (
    EdgeRecord,
    MutationOperation,
    MutationResult,
    NodeRecord,
    QueryResultRow,
    TypeDefinition,
)


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


@runtime_checkable
class ITypeDefinitionRepository(Protocol):
    """Repository for storing and retrieving type definitions.

    Type definitions are created from DEFINE operations and used to
    validate CREATE operations. This protocol enables swappable storage
    implementations (in-memory, database, etc.).
    """

    def save(self, type_def: TypeDefinition) -> None:
        """Save a type definition.

        Args:
            type_def: The type definition to save

        Note:
            If a definition with the same label and entity_type already exists,
            it should be replaced.
        """
        ...

    def get(self, label: str, entity_type: str) -> TypeDefinition | None:
        """Retrieve a type definition by label and entity type.

        Args:
            label: The type label (e.g., "Person", "KNOWS")
            entity_type: Either "node" or "edge"

        Returns:
            The type definition if found, None otherwise
        """
        ...

    def get_all(self) -> list[TypeDefinition]:
        """Get all stored type definitions.

        Returns:
            List of all type definitions
        """
        ...

    def delete(self, label: str, entity_type: str) -> bool:
        """Delete a type definition.

        Args:
            label: The type label
            entity_type: Either "node" or "edge"

        Returns:
            True if deleted, False if not found
        """
        ...


@runtime_checkable
class IMutationApplier(Protocol):
    """Interface for applying mutation operations to the graph database.

    This protocol defines the contract for components that execute
    mutation operations. The application layer depends on this interface
    rather than concrete infrastructure implementations.
    """

    def apply_batch(
        self,
        operations: list[MutationOperation],
    ) -> MutationResult:
        """Apply a batch of mutations atomically.

        All operations are executed within a single transaction. If any operation
        fails, the entire batch is rolled back.

        Args:
            operations: List of mutation operations to apply

        Returns:
            MutationResult with success status and operation count
        """
        ...
