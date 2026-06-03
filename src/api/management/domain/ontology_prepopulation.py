"""Prepopulation validation rules for ontology authoring."""

from __future__ import annotations

from management.domain.value_objects import EdgeTypeDefinition, OntologyConfig


class PrepopulationValidationError(ValueError):
    """Raised when ontology prepopulation flags violate authoring rules."""


def relationship_readiness_key(edge: EdgeTypeDefinition) -> str:
    """Stable readiness identifier aligned with design-artifacts relationship keys."""
    source = edge.source_labels[0] if edge.source_labels else "?"
    target = edge.target_labels[0] if edge.target_labels else "?"
    return f"{source}|{edge.label}|{target}"


def validate_ontology_prepopulation(config: OntologyConfig) -> None:
    """Ensure prepopulated relationship types only connect prepopulated entity types."""
    node_by_label = {node_type.label: node_type for node_type in config.node_types}

    for edge_type in config.edge_types:
        if not edge_type.prepopulated:
            continue
        if not edge_type.source_labels or not edge_type.target_labels:
            raise PrepopulationValidationError(
                f"Relationship type `{edge_type.label}` cannot be prepopulated without "
                "source_labels and target_labels"
            )
        for source_label in edge_type.source_labels:
            source_type = node_by_label.get(source_label)
            if source_type is None or not source_type.prepopulated:
                raise PrepopulationValidationError(
                    f"Relationship type `{edge_type.label}` is prepopulated but source "
                    f"entity type `{source_label}` is not prepopulated"
                )
        for target_label in edge_type.target_labels:
            target_type = node_by_label.get(target_label)
            if target_type is None or not target_type.prepopulated:
                raise PrepopulationValidationError(
                    f"Relationship type `{edge_type.label}` is prepopulated but target "
                    f"entity type `{target_label}` is not prepopulated"
                )
