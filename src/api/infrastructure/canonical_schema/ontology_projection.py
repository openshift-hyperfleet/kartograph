"""Map stored canonical schema rows to Management ontology configs."""

from __future__ import annotations

import logging

from graph.infrastructure.postgres_kg_type_definition_store import (
    StoredKnowledgeGraphTypeDefinition,
)
from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
    _coerce_bool,
)

logger = logging.getLogger(__name__)


def _optional_metadata_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
                    prepopulated=_coerce_bool(
                        stored.metadata.get("prepopulated"), default=False
                    ),
                    prepopulated_instance_count=int(
                        stored.metadata.get("prepopulated_instance_count", 0)
                    ),
                    instance_generator=_optional_metadata_str(
                        stored.metadata.get("instance_generator")
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
                    prepopulated=_coerce_bool(
                        stored.metadata.get("prepopulated"), default=False
                    ),
                    prepopulated_instance_count=int(
                        stored.metadata.get("prepopulated_instance_count", 0)
                    ),
                    instance_generator=_optional_metadata_str(
                        stored.metadata.get("instance_generator")
                    ),
                    bidirectional=bool(stored.metadata.get("bidirectional", False)),
                    inverse_label=_optional_metadata_str(
                        stored.metadata.get("inverse_label")
                    ),
                    inverse_of=_optional_metadata_str(
                        stored.metadata.get("inverse_of")
                    ),
                    auto_generated=bool(stored.metadata.get("auto_generated", False)),
                    bidirectional_pair_key=_optional_metadata_str(
                        stored.metadata.get("bidirectional_pair_key")
                    ),
                )
            )

    if unknown := {
        stored.entity_type
        for stored in stored_definitions
        if stored.entity_type not in {"node", "edge"}
    }:
        logger.warning(
            "Skipping canonical schema rows with unexpected entity_type values: %s",
            sorted(unknown),
        )

    return OntologyConfig(
        node_types=tuple(node_types),
        edge_types=tuple(edge_types),
    )
