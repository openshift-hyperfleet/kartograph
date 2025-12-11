"""In-memory implementation of ITypeDefinitionRepository.

This is a stub implementation for type definition storage. In production,
this could be replaced with a database-backed implementation that persists
type definitions across restarts.

The in-memory implementation is sufficient for MVP and enables proper
separation of concerns via the repository protocol.
"""

from __future__ import annotations

from graph.domain.value_objects import TypeDefinition


class InMemoryTypeDefinitionRepository:
    """In-memory storage for type definitions.

    Stores type definitions in a dictionary keyed by (label, entity_type).
    This implementation loses data on restart but is sufficient for MVP
    and testing purposes.

    Thread-safety: This implementation is NOT thread-safe. In production,
    use appropriate locking or a database-backed implementation.
    """

    def __init__(self) -> None:
        """Initialize an empty type definition store."""
        self._store: dict[tuple[str, str], TypeDefinition] = {}

    def save(self, type_def: TypeDefinition) -> None:
        """Save a type definition.

        Args:
            type_def: The type definition to save

        Note:
            If a definition with the same label and entity_type already exists,
            it will be replaced.
        """
        key = (type_def.label, type_def.entity_type)
        self._store[key] = type_def

    def get(self, label: str, entity_type: str) -> TypeDefinition | None:
        """Retrieve a type definition by label and entity type.

        Args:
            label: The type label (e.g., "Person", "KNOWS")
            entity_type: Either "node" or "edge"

        Returns:
            The type definition if found, None otherwise
        """
        key = (label, entity_type)
        return self._store.get(key)

    def get_all(self) -> list[TypeDefinition]:
        """Get all stored type definitions.

        Returns:
            List of all type definitions
        """
        return list(self._store.values())

    def delete(self, label: str, entity_type: str) -> bool:
        """Delete a type definition.

        Args:
            label: The type label
            entity_type: Either "node" or "edge"

        Returns:
            True if deleted, False if not found
        """
        key = (label, entity_type)
        if key in self._store:
            del self._store[key]
            return True
        return False
