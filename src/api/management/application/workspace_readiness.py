"""Workspace bootstrap readiness evaluation for knowledge graphs."""

from __future__ import annotations

from management.domain.ontology_prepopulation import relationship_readiness_key
from management.domain.relationship_pairing import is_primary_relationship_for_display
from management.domain.value_objects import OntologyConfig, WorkspaceReadinessStatus


def evaluate_workspace_readiness(
    ontology: OntologyConfig | None,
) -> WorkspaceReadinessStatus:
    """Evaluate transition readiness flags from canonical schema metadata."""
    node_type_count = len(ontology.node_types) if ontology else 0
    edge_type_count = len(ontology.edge_types) if ontology else 0

    prepopulated_without_instances: tuple[str, ...] = ()
    prepopulated_relationships_without_instances: tuple[str, ...] = ()
    if ontology is not None:
        prepopulated_without_instances = tuple(
            node_type.label
            for node_type in ontology.node_types
            if node_type.prepopulated and node_type.prepopulated_instance_count <= 0
        )
        prepopulated_relationships_without_instances = tuple(
            relationship_readiness_key(edge_type)
            for edge_type in ontology.edge_types
            if edge_type.prepopulated
            and edge_type.prepopulated_instance_count <= 0
            and is_primary_relationship_for_display(edge_type)
        )

    has_min_entities = node_type_count >= 1
    has_min_relationships = edge_type_count >= 1
    prepopulated_ready = (
        len(prepopulated_without_instances) == 0
        and len(prepopulated_relationships_without_instances) == 0
    )

    blocking_reasons: list[str] = []
    if not has_min_entities:
        blocking_reasons.append("At least one entity type is required")
    if not has_min_relationships:
        blocking_reasons.append("At least one relationship type is required")
    if prepopulated_without_instances:
        labels = ", ".join(prepopulated_without_instances)
        blocking_reasons.append(
            f"Prepopulated entity types require instances before transition: {labels}"
        )
    if prepopulated_relationships_without_instances:
        labels = ", ".join(prepopulated_relationships_without_instances)
        blocking_reasons.append(
            "Prepopulated relationship types require instances before transition: "
            f"{labels}"
        )

    return WorkspaceReadinessStatus(
        has_minimum_entity_types=has_min_entities,
        has_minimum_relationship_types=has_min_relationships,
        prepopulated_types_ready=prepopulated_ready,
        prepopulated_types_without_instances=prepopulated_without_instances,
        prepopulated_relationship_types_without_instances=(
            prepopulated_relationships_without_instances
        ),
        blocking_reasons=tuple(blocking_reasons),
    )


def prepopulated_gaps_from_live_counts(
    ontology: OntologyConfig | None,
    *,
    entity_instance_counts: dict[str, int],
    relationship_instance_counts: dict[str, int],
) -> dict[str, tuple[str, ...]]:
    """Return prepopulated type labels/keys with zero live graph instances."""
    if ontology is None:
        return {
            "entity_types_without_instances": (),
            "relationship_types_without_instances": (),
        }

    entity_gaps = tuple(
        node_type.label
        for node_type in ontology.node_types
        if node_type.prepopulated
        and entity_instance_counts.get(node_type.label, 0) <= 0
    )
    relationship_gaps = tuple(
        relationship_readiness_key(edge_type)
        for edge_type in ontology.edge_types
        if edge_type.prepopulated
        and relationship_instance_counts.get(relationship_readiness_key(edge_type), 0)
        <= 0
        and is_primary_relationship_for_display(edge_type)
    )
    return {
        "entity_types_without_instances": entity_gaps,
        "relationship_types_without_instances": relationship_gaps,
    }
