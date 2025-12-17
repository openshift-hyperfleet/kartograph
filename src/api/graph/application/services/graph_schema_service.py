"""Schema/Ontology service for the Graph bounded context.

Provides access to graph type definitions (ontology/schema).
"""

from __future__ import annotations

from graph.application.observability.default_schema_service_probe import (
    DefaultSchemaServiceProbe,
)
from graph.application.observability.schema_service_probe import SchemaServiceProbe
from graph.domain.value_objects import TypeDefinition
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
