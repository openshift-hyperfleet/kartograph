"""Schema/Ontology service for the Graph bounded context.

Provides access to graph type definitions (ontology/schema).
"""

from __future__ import annotations

from graph.application.observability.default_schema_service_probe import (
    DefaultSchemaServiceProbe,
)
from graph.application.observability.schema_service_probe import SchemaServiceProbe
from graph.domain.value_objects import EntityType, TypeDefinition
from graph.ports.repositories import ITypeDefinitionRepository


class GraphSchemaService:
    """Application service for graph schema/ontology operations.

    Provides read access to type definitions that describe the structure
    of the knowledge graph.
    """

    def __init__(
        self,
        type_definition_repository: ITypeDefinitionRepository,
        probe: SchemaServiceProbe | None = None,
    ):
        """Initialize the service.

        Args:
            type_definition_repository: Repository for type definitions
            probe: Optional domain probe for observability
        """
        self._type_definition_repository = type_definition_repository
        self._probe = probe or DefaultSchemaServiceProbe()

    def get_ontology(self) -> list[TypeDefinition]:
        """Get all type definitions (graph ontology/schema).

        Returns:
            List of all type definitions for nodes and edges
        """
        definitions = self._type_definition_repository.get_all()
        self._probe.ontology_retrieved(count=len(definitions))
        return definitions

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
        return self._get_labels_for_entity_type(
            EntityType.NODE, search=search, has_property=has_property
        )

    def get_edge_labels(
        self,
        search: str | None = None,
    ) -> list[str]:
        """Get list of edge type labels.

        Args:
            search: Optional search term to filter labels (case-insensitive)

        Returns:
            List of edge type labels matching filters
        """
        return self._get_labels_for_entity_type(EntityType.EDGE, search=search)

    def get_node_schema(self, label: str) -> TypeDefinition | None:
        """Get full schema for a specific node type.

        Args:
            label: The node type label

        Returns:
            TypeDefinition if found, None otherwise
        """
        return self._type_definition_repository.get(label, "node")

    def get_edge_schema(self, label: str) -> TypeDefinition | None:
        """Get full schema for a specific edge type.

        Args:
            label: The edge type label

        Returns:
            TypeDefinition if found, None otherwise
        """
        return self._type_definition_repository.get(label, "edge")

    def _get_labels_for_entity_type(
        self,
        entity_type: EntityType,
        search: str | None = None,
        has_property: str | None = None,
    ) -> list[str]:
        """Get filtered list of labels for a specific entity type.

        Args:
            entity_type: EntityType.NODE or EntityType.EDGE
            search: Optional search term (case-insensitive)
            has_property: Optional property name filter

        Returns:
            List of labels matching all filters
        """
        definitions = self._type_definition_repository.get_all()

        # Filter by entity type
        filtered = [d for d in definitions if d.entity_type == entity_type]

        # Apply search filter
        if search:
            search_lower = search.lower()
            filtered = [d for d in filtered if search_lower in d.label.lower()]

        # Apply has_property filter
        if has_property:
            print(filtered)
            filtered = [
                d
                for d in filtered
                if has_property in d.required_properties
                or has_property in d.optional_properties
            ]

        return [d.label for d in filtered]
