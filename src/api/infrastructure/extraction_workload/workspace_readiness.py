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
    is_primary_relationship_for_display,
    resolve_inverse_label_for_primary,
    twin_validation_errors,
)
from management.domain.value_objects import EdgeTypeDefinition, NodeTypeDefinition, OntologyConfig


def _entity_scanner_path(label: str) -> str:
    return f"instance_generators/{label}.py"


def _entity_output_paths(label: str) -> tuple[str, str]:
    return (
        f"instance_generators/out/{label}_instances.json",
        f"instance_generators/out/{label}_instances.jsonl",
    )


def _relationship_scanner_path(*, source: str, relationship: str, target: str) -> str:
    return f"instance_generators/{source}_{relationship}_{target}.py"


def _relationship_output_paths(*, source: str, relationship: str, target: str) -> tuple[str, str]:
    stem = f"{source}_{relationship}_{target}"
    return (
        f"instance_generators/out/{stem}_instances.json",
        f"instance_generators/out/{stem}_instances.jsonl",
    )


def _build_prepopulation_tasks(
    *,
    ontology: OntologyConfig | None,
    live_entity_gaps: list[str],
    live_relationship_gaps: list[str],
    entity_instance_counts: dict[str, int],
    relationship_instance_counts: dict[str, int],
) -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    if ontology is None:
        return tasks

    for label in live_entity_gaps:
        node_type = next((nt for nt in ontology.node_types if nt.label == label), None)
        live_count = entity_instance_counts.get(label, 0)
        output_json, output_jsonl = _entity_output_paths(label)
        tasks.append(
            {
                "kind": "entity",
                "order": 1,
                "blocking_types": [],
                "label": label,
                "live_instance_count": live_count,
                "scanner_path": _entity_scanner_path(label),
                "output_json": output_json,
                "output_jsonl": output_jsonl,
                "run_command": (
                    f"python3 instance_generators/run_scanner.py {label} --entity"
                ),
                "required_properties": list(node_type.required_properties) if node_type else [],
                "optional_properties": list(node_type.optional_properties) if node_type else [],
                "action": (
                    f"Copy _entity_scanner.example.py to {_entity_scanner_path(label)} "
                    f"(filename must match label exactly), then "
                    f"`python3 instance_generators/run_scanner.py {label} --entity` "
                    "and apply the printed jsonl_path."
                ),
            }
        )

    for key in live_relationship_gaps:
        edge_type = next(
            (et for et in ontology.edge_types if relationship_readiness_key(et) == key),
            None,
        )
        source = edge_type.source_labels[0] if edge_type and edge_type.source_labels else ""
        target = edge_type.target_labels[0] if edge_type and edge_type.target_labels else ""
        rel = edge_type.label if edge_type else ""
        scanner = (
            _relationship_scanner_path(source=source, relationship=rel, target=target)
            if source and target and rel
            else f"instance_generators/{key}.py"
        )
        output_json, output_jsonl = (
            _relationship_output_paths(source=source, relationship=rel, target=target)
            if source and target and rel
            else (
                f"instance_generators/out/{key}_instances.json",
                f"instance_generators/out/{key}_instances.jsonl",
            )
        )
        run_command = (
            "python3 instance_generators/run_scanner.py "
            f"--relationship --source {source} --rel {rel} --target {target}"
            if source and target and rel
            else None
        )
        tasks.append(
            {
                "kind": "relationship",
                "order": 2,
                "blocking_types": [source, target] if source and target else [],
                "key": key,
                "relationship_type": rel,
                "source_entity_type": source,
                "target_entity_type": target,
                "live_instance_count": relationship_instance_counts.get(key, 0),
                "scanner_path": scanner,
                "output_json": output_json,
                "output_jsonl": output_jsonl,
                "run_command": run_command,
                "action": (
                    f"Copy _relationship_scanner.example.py to {scanner}, then "
                    f"`{run_command}` and apply the printed jsonl_path."
                    if run_command
                    else "Run relationship steps in PREPOPULATION_WORKFLOW.md."
                ),
            }
        )
    return tasks


def _build_next_action(
    *,
    live_entity_gaps: list[str],
    live_relationship_gaps: list[str],
    transition_eligible: bool,
    blocking_reasons: list[str],
) -> str:
    if live_entity_gaps:
        label = live_entity_gaps[0]
        return (
            f"Run entity prepopulation for `{label}`: create {_entity_scanner_path(label)} "
            "from _entity_scanner.example.py (case-sensitive filename), then "
            f"`python3 instance_generators/run_scanner.py {label} --entity` and apply the "
            "printed jsonl_path."
        )
    if live_relationship_gaps:
        key = live_relationship_gaps[0]
        return (
            f"Run relationship prepopulation for `{key}` using "
            "_relationship_scanner.example.py, run_scanner.py --relationship, and apply the "
            "printed jsonl_path."
        )
    if transition_eligible:
        return (
            "All prepopulated types have live instances. Bootstrap prepopulation is complete."
        )
    if blocking_reasons:
        return "Resolve blocking_reasons before continuing prepopulation."
    return "Review kartograph_get_workspace_readiness and continue schema bootstrap."


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
            "required_properties": list(node_type.required_properties),
            "optional_properties": list(node_type.optional_properties),
            "scanner_path": _entity_scanner_path(node_type.label),
            "needs_instances": entity_instance_counts.get(node_type.label, 0) == 0,
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
            "required_properties": list(edge_type.properties),
            "scanner_path": _relationship_scanner_path(
                source=edge_type.source_labels[0] if edge_type.source_labels else "source",
                relationship=edge_type.label,
                target=edge_type.target_labels[0] if edge_type.target_labels else "target",
            ),
            "needs_instances": relationship_instance_counts.get(
                relationship_readiness_key(edge_type),
                0,
            )
            == 0,
        }
        for edge_type in (ontology.edge_types if ontology else ())
        if edge_type.prepopulated and is_primary_relationship_for_display(edge_type)
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

    prepopulation_tasks = _build_prepopulation_tasks(
        ontology=ontology,
        live_entity_gaps=list(live_entity_gaps),
        live_relationship_gaps=list(live_relationship_gaps),
        entity_instance_counts=entity_instance_counts,
        relationship_instance_counts=relationship_instance_counts,
    )
    next_action = _build_next_action(
        live_entity_gaps=list(live_entity_gaps),
        live_relationship_gaps=list(live_relationship_gaps),
        transition_eligible=transition_eligible,
        blocking_reasons=blocking_reasons,
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
        "prepopulation_tasks": prepopulation_tasks,
        "next_action": next_action,
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
