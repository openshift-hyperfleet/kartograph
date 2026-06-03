"""Map stored canonical schema rows to Management ontology configs."""

from __future__ import annotations

from graph.infrastructure.postgres_kg_type_definition_store import (
    StoredKnowledgeGraphTypeDefinition,
)
from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
)


def stored_definitions_to_ontology_config(
    stored_definitions: list[StoredKnowledgeGraphTypeDefinition],
) -> OntologyConfig:
    """Project graph-native type definitions to Management OntologyConfig."""
    node_types: list[NodeTypeDefinition] = []
    edge_types: list[EdgeTypeDefinition] = []

    for stored in stored_definitions:
        if stored.entity_type == "node":
            node_types.append(
                NodeTypeDefinition(
                    label=stored.label,
                    description=stored.description,
                    required_properties=stored.required_properties,
                    optional_properties=stored.optional_properties,
                    prepopulated=bool(stored.metadata.get("prepopulated", False)),
                    prepopulated_instance_count=int(
                        stored.metadata.get("prepopulated_instance_count", 0)
                    ),
                )
            )
        elif stored.entity_type == "edge":
            edge_types.append(
                EdgeTypeDefinition(
                    label=stored.label,
                    description=stored.description,
                    source_labels=tuple(stored.metadata.get("source_labels", [])),
                    target_labels=tuple(stored.metadata.get("target_labels", [])),
                    properties=tuple(stored.metadata.get("properties", [])),
                    prepopulated=bool(stored.metadata.get("prepopulated", False)),
                    prepopulated_instance_count=int(
                        stored.metadata.get("prepopulated_instance_count", 0)
                    ),
                )
            )

    return OntologyConfig(
        node_types=tuple(node_types),
        edge_types=tuple(edge_types),
    )
