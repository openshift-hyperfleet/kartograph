"""Bridge Management ontology configs to graph DEFINE mutation operations."""

from __future__ import annotations

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)
from management.domain.value_objects import OntologyConfig


def ontology_config_to_define_operations(
    config: OntologyConfig,
) -> list[MutationOperation]:
    """Convert an ontology config into DEFINE mutation operations."""
    operations: list[MutationOperation] = []

    for node_type in config.node_types:
        operations.append(
            MutationOperation(
                op=MutationOperationType.DEFINE,
                type=EntityType.NODE,
                label=node_type.label,
                description=node_type.description or node_type.label,
                required_properties=set(node_type.required_properties),
                optional_properties=set(node_type.optional_properties),
            )
        )

    for edge_type in config.edge_types:
        operations.append(
            MutationOperation(
                op=MutationOperationType.DEFINE,
                type=EntityType.EDGE,
                label=edge_type.label,
                description=edge_type.description or edge_type.label,
                required_properties=set(edge_type.properties),
                optional_properties=set(),
            )
        )

    return operations


def node_type_metadata(node_type) -> dict:
    """Serialize node-type authoring metadata for canonical storage."""
    metadata = {
        "prepopulated": node_type.prepopulated,
        "prepopulated_instance_count": node_type.prepopulated_instance_count,
    }
    if node_type.instance_generator:
        metadata["instance_generator"] = node_type.instance_generator
    return metadata


def edge_type_metadata(edge_type) -> dict:
    """Serialize edge-type authoring metadata for canonical storage."""
    metadata = {
        "source_labels": list(edge_type.source_labels),
        "target_labels": list(edge_type.target_labels),
        "properties": list(edge_type.properties),
        "prepopulated": edge_type.prepopulated,
        "prepopulated_instance_count": edge_type.prepopulated_instance_count,
    }
    if edge_type.instance_generator:
        metadata["instance_generator"] = edge_type.instance_generator
    if edge_type.bidirectional:
        metadata["bidirectional"] = True
    if edge_type.inverse_label:
        metadata["inverse_label"] = edge_type.inverse_label
    if edge_type.inverse_of:
        metadata["inverse_of"] = edge_type.inverse_of
    if edge_type.auto_generated:
        metadata["auto_generated"] = True
    if edge_type.bidirectional_pair_key:
        metadata["bidirectional_pair_key"] = edge_type.bidirectional_pair_key
    return metadata
