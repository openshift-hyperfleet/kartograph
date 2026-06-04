"""Unit tests for canonical schema ontology projection."""

from __future__ import annotations

from graph.infrastructure.postgres_kg_type_definition_store import (
    StoredKnowledgeGraphTypeDefinition,
)
from infrastructure.canonical_schema.ontology_projection import (
    stored_definitions_to_ontology_config,
)
from management.domain.value_objects import NodeTypeDefinition


def test_stored_definitions_restore_instance_generator_metadata() -> None:
    config = stored_definitions_to_ontology_config(
        [
            StoredKnowledgeGraphTypeDefinition(
                label="service",
                entity_type="node",
                description="Service",
                required_properties=("name",),
                optional_properties=(),
                metadata={
                    "prepopulated": True,
                    "prepopulated_instance_count": 0,
                    "instance_generator": "my_service.py",
                },
            )
        ]
    )

    assert config.node_types == (
        NodeTypeDefinition(
            label="service",
            description="Service",
            required_properties=("name",),
            prepopulated=True,
            instance_generator="my_service.py",
        ),
    )
