"""Schema/ontology port for the Query bounded context.

Defines the interface for accessing graph type definitions without
coupling to the Graph context's implementation.
"""

from typing import Protocol


class EntityTypeLike(Protocol):
    """Protocol for entity type enums.

    Matches the structure of graph.domain.value_objects.EntityType
    without importing from the Graph context.
    """

    @property
    def value(self) -> str:
        """Get the string value of the entity type."""
        ...


class TypeDefinitionLike(Protocol):
    """Protocol for type definition objects.

    Defines the expected structure for type definitions returned by
    schema service methods. Matches graph.domain.value_objects.TypeDefinition
    without creating import-time coupling.

    This enables full IDE autocomplete and type checking while maintaining
    DDD bounded context isolation.
    """

    label: str
    entity_type: EntityTypeLike
    description: str
    example_file_path: str
    example_in_file_path: str
    required_properties: set[str]
    optional_properties: set[str]


class ISchemaService(Protocol):
    """Interface for schema/ontology access.

    This port defines what the Query context needs for schema discovery,
    allowing the Graph context's GraphSchemaService to be injected at
    runtime without creating static import dependencies.
    """

    def get_ontology(self) -> list[TypeDefinitionLike]:
        """Get all type definitions (full graph ontology/schema).

        Returns:
            List of all type definitions for nodes and edges
        """
        ...

    def get_node_labels(
        self,
        search: str | None = None,
        has_property: str | None = None,
    ) -> list[str]:
        """Get list of node type labels.

        Args:
            search: Optional search term to filter labels (case-insensitive)
            has_property: Optional property name filter

        Returns:
            List of node type labels matching filters
        """
        ...

    def get_edge_labels(self, search: str | None = None) -> list[str]:
        """Get list of edge type labels.

        Args:
            search: Optional search term to filter labels (case-insensitive)

        Returns:
            List of edge type labels matching filters
        """
        ...

    def get_node_schema(self, label: str) -> TypeDefinitionLike | None:
        """Get full schema for a specific node type.

        Args:
            label: The node type label

        Returns:
            TypeDefinition if found, None otherwise
        """
        ...

    def get_edge_schema(self, label: str) -> TypeDefinitionLike | None:
        """Get full schema for a specific edge type.

        Args:
            label: The edge type label

        Returns:
            TypeDefinition if found, None otherwise
        """
        ...
