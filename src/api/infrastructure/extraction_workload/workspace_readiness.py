"""Build workspace readiness snapshots for Graph Management Assistant tools."""

from __future__ import annotations

from dataclasses import replace

from management.application.workspace_readiness import (
    evaluate_workspace_readiness,
    prepopulated_gaps_from_live_counts,
)
from management.domain.ontology_prepopulation import relationship_readiness_key
from management.domain.relationship_pairing import (
    bidirectional_pair_key,
    resolve_inverse_label_for_primary,
    twin_validation_errors,
)
from management.domain.value_objects import EdgeTypeDefinition, NodeTypeDefinition, OntologyConfig


async def build_workload_readiness_snapshot(
    *,
    ontology: OntologyConfig | None,
    knowledge_graph_id: str,
    tenant_id: str,
    graph_reader,
) -> dict[str, object]:
    """Merge canonical readiness metadata with live graph instance counts."""
    metadata_readiness = evaluate_workspace_readiness(ontology)

    entity_instance_counts: dict[str, int] = {}
    relationship_instance_counts: dict[str, int] = {}

    if ontology is not None:
        for node_type in ontology.node_types:
            if not node_type.prepopulated:
                continue
            entity_instance_counts[node_type.label] = await graph_reader.count_entity_instances_by_type(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                entity_type=node_type.label,
            )

        for edge_type in ontology.edge_types:
            if not edge_type.prepopulated:
                continue
            key = relationship_readiness_key(edge_type)
            source_label = edge_type.source_labels[0] if edge_type.source_labels else None
            target_label = edge_type.target_labels[0] if edge_type.target_labels else None
            relationship_instance_counts[key] = await graph_reader.count_relationship_instances(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                relationship_type=edge_type.label,
                source_entity_type=source_label,
                target_entity_type=target_label,
            )

    live_gaps = prepopulated_gaps_from_live_counts(
        ontology,
        entity_instance_counts=entity_instance_counts,
        relationship_instance_counts=relationship_instance_counts,
    )

    prepopulated_entity_types = [
        {
            "label": node_type.label,
            "metadata_instance_count": node_type.prepopulated_instance_count,
            "live_instance_count": entity_instance_counts.get(node_type.label, 0),
        }
        for node_type in (ontology.node_types if ontology else ())
        if node_type.prepopulated
    ]

    prepopulated_relationship_types = [
        {
            "key": relationship_readiness_key(edge_type),
            "relationship_type": edge_type.label,
            "source_entity_type": edge_type.source_labels[0] if edge_type.source_labels else "",
            "target_entity_type": edge_type.target_labels[0] if edge_type.target_labels else "",
            "metadata_instance_count": edge_type.prepopulated_instance_count,
            "live_instance_count": relationship_instance_counts.get(
                relationship_readiness_key(edge_type),
                0,
            ),
        }
        for edge_type in (ontology.edge_types if ontology else ())
        if edge_type.prepopulated
    ]

    live_entity_gaps = live_gaps["entity_types_without_instances"]
    live_relationship_gaps = live_gaps["relationship_types_without_instances"]
    live_prepopulated_ready = len(live_entity_gaps) == 0 and len(live_relationship_gaps) == 0

    blocking_reasons = list(metadata_readiness.blocking_reasons)
    if live_entity_gaps and not any("Prepopulated entity types" in reason for reason in blocking_reasons):
        blocking_reasons.append(
            "Live graph missing prepopulated entity instances: "
            + ", ".join(live_entity_gaps)
        )
    if live_relationship_gaps and not any(
        "Prepopulated relationship types" in reason for reason in blocking_reasons
    ):
        blocking_reasons.append(
            "Live graph missing prepopulated relationship instances: "
            + ", ".join(live_relationship_gaps)
        )

    if ontology is not None and graph_reader is not None:
        bidirectional_counts: dict[str, int] = {}
        for edge_type in ontology.edge_types:
            if edge_type.auto_generated or edge_type.inverse_of or not edge_type.bidirectional:
                continue
            if not edge_type.source_labels or not edge_type.target_labels:
                continue
            source_label = edge_type.source_labels[0]
            target_label = edge_type.target_labels[0]
            primary_key = bidirectional_pair_key(
                source_label=source_label,
                relationship_label=edge_type.label,
                target_label=target_label,
            )
            inverse_label = resolve_inverse_label_for_primary(edge_type)
            inverse_key = bidirectional_pair_key(
                source_label=target_label,
                relationship_label=inverse_label,
                target_label=source_label,
            )
            bidirectional_counts[primary_key] = await graph_reader.count_relationship_instances(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                relationship_type=edge_type.label,
                source_entity_type=source_label,
                target_entity_type=target_label,
            )
            bidirectional_counts[inverse_key] = await graph_reader.count_relationship_instances(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                relationship_type=inverse_label,
                source_entity_type=target_label,
                target_entity_type=source_label,
            )
        blocking_reasons.extend(
            twin_validation_errors(
                ontology=ontology,
                relationship_counts=bidirectional_counts,
            )
        )

    transition_eligible = (
        metadata_readiness.has_minimum_entity_types
        and metadata_readiness.has_minimum_relationship_types
        and live_prepopulated_ready
    )

    return {
        "knowledge_graph_id": knowledge_graph_id,
        "has_minimum_entity_types": metadata_readiness.has_minimum_entity_types,
        "has_minimum_relationship_types": metadata_readiness.has_minimum_relationship_types,
        "prepopulated_types_ready_metadata": metadata_readiness.prepopulated_types_ready,
        "prepopulated_types_ready_live": live_prepopulated_ready,
        "prepopulated_types_without_instances_metadata": list(
            metadata_readiness.prepopulated_types_without_instances
        ),
        "prepopulated_relationship_types_without_instances_metadata": list(
            metadata_readiness.prepopulated_relationship_types_without_instances
        ),
        "prepopulated_entity_types_without_instances_live": list(live_entity_gaps),
        "prepopulated_relationship_types_without_instances_live": list(live_relationship_gaps),
        "prepopulated_entity_types": prepopulated_entity_types,
        "prepopulated_relationship_types": prepopulated_relationship_types,
        "blocking_reasons": blocking_reasons,
        "transition_eligible": transition_eligible,
    }


async def sync_prepopulated_instance_counts(
    *,
    ontology: OntologyConfig,
    knowledge_graph_id: str,
    tenant_id: str,
    graph_reader,
) -> OntologyConfig:
    """Refresh ontology metadata counts from live graph instance totals."""
    updated_nodes: list[NodeTypeDefinition] = []
    nodes_changed = False
    for node_type in ontology.node_types:
        if not node_type.prepopulated:
            updated_nodes.append(node_type)
            continue
        live_count = await graph_reader.count_entity_instances_by_type(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            entity_type=node_type.label,
        )
        if live_count != node_type.prepopulated_instance_count:
            nodes_changed = True
        updated_nodes.append(
            replace(node_type, prepopulated_instance_count=live_count),
        )

    updated_edges: list[EdgeTypeDefinition] = []
    edges_changed = False
    for edge_type in ontology.edge_types:
        if not edge_type.prepopulated:
            updated_edges.append(edge_type)
            continue
        source_label = edge_type.source_labels[0] if edge_type.source_labels else None
        target_label = edge_type.target_labels[0] if edge_type.target_labels else None
        live_count = await graph_reader.count_relationship_instances(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            relationship_type=edge_type.label,
            source_entity_type=source_label,
            target_entity_type=target_label,
        )
        if live_count != edge_type.prepopulated_instance_count:
            edges_changed = True
        updated_edges.append(
            replace(edge_type, prepopulated_instance_count=live_count),
        )

    if not nodes_changed and not edges_changed:
        return ontology

    return replace(
        ontology,
        node_types=tuple(updated_nodes),
        edge_types=tuple(updated_edges),
    )
