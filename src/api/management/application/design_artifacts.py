"""Pure builders for knowledge graph design artifact views."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from management.domain.relationship_pairing import (
    is_primary_relationship_for_display,
    is_secondary_bidirectional_edge,
    resolve_inverse_label_for_primary,
)
from management.domain.value_objects import EdgeTypeDefinition, OntologyConfig

_SYSTEM_NODE_PROPERTIES = frozenset(
    {
        "id",
        "slug",
        "data_source_id",
        "source_path",
        "knowledge_graph_id",
        "graph_id",
        "name",
    }
)


def _instance_properties(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in raw.items()
        if key not in _SYSTEM_NODE_PROPERTIES and not key.startswith("_")
    }


def _reverse_relationship_label(edge_type: EdgeTypeDefinition) -> str | None:
    if edge_type.auto_generated or edge_type.inverse_of:
        return None
    if not edge_type.bidirectional:
        return None
    return resolve_inverse_label_for_primary(edge_type)


def build_design_artifacts(
    *,
    knowledge_graph_id: str,
    ontology: OntologyConfig | None,
    graph_data: dict[str, Any],
    limit: int,
) -> dict[str, Any]:
    """Merge canonical ontology with live AGE graph instances for the Dev UI."""
    nodes = [
        node
        for node in graph_data.get("nodes", [])
        if node.get("knowledge_graph_id") == knowledge_graph_id and not node.get("_redacted")
    ]
    edges = [
        edge
        for edge in graph_data.get("edges", [])
        if edge.get("knowledge_graph_id") == knowledge_graph_id and not edge.get("_redacted")
    ]

    node_by_age_id = {str(node.get("id")): node for node in nodes if node.get("id")}

    def _node_instance(node: dict[str, Any]) -> dict[str, Any]:
        slug = str(node.get("slug") or node.get("domainId") or node.get("id") or "")
        return {
            "slug": slug,
            "properties": _instance_properties(node),
        }

    full_instances_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in sorted(
        nodes,
        key=lambda item: (
            str(item.get("type") or ""),
            str(item.get("slug") or item.get("domainId") or item.get("id") or ""),
        ),
    ):
        entity_type = str(node.get("type") or "unknown")
        full_instances_by_type[entity_type].append(_node_instance(node))

    instances_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sorted_nodes = sorted(
        nodes,
        key=lambda node: (
            str(node.get("type") or ""),
            str(node.get("slug") or node.get("domainId") or node.get("id") or ""),
        ),
    )
    truncated_nodes = sorted_nodes[:limit]

    for node in truncated_nodes:
        entity_type = str(node.get("type") or "unknown")
        instances_by_type[entity_type].append(_node_instance(node))

    entities: dict[str, dict[str, Any]] = {}
    if ontology is not None:
        for node_type in ontology.node_types:
            required = list(node_type.required_properties)
            optional = list(node_type.optional_properties)
            property_definitions = {
                prop: prop.replace("_", " ").strip() or prop
                for prop in (*required, *optional)
            }
            type_instances = instances_by_type.get(node_type.label, [])
            total_instances = len(full_instances_by_type.get(node_type.label, []))
            entities[node_type.label] = {
                "type": node_type.label,
                "description": node_type.description,
                "required_properties": required,
                "optional_properties": optional,
                "property_definitions": property_definitions,
                "prepopulated_instances": node_type.prepopulated,
                "instance_count": total_instances,
                "instances_returned": len(type_instances),
                "instances_truncated": total_instances > len(type_instances),
                "instances": type_instances,
            }

    for entity_type, type_instances in instances_by_type.items():
        if entity_type in entities:
            continue
        total_instances = len(full_instances_by_type.get(entity_type, []))
        entities[entity_type] = {
            "type": entity_type,
            "description": "",
            "required_properties": [],
            "optional_properties": [],
            "property_definitions": {},
            "prepopulated_instances": False,
            "instance_count": total_instances,
            "instances_returned": len(type_instances),
            "instances_truncated": total_instances > len(type_instances),
            "instances": type_instances,
        }

    relationship_instances: dict[str, list[dict[str, Any]]] = defaultdict(list)
    full_relationship_instances: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def _edge_instance(edge: dict[str, Any]) -> dict[str, Any] | None:
        source_node = node_by_age_id.get(str(edge.get("source")))
        target_node = node_by_age_id.get(str(edge.get("target")))
        if source_node is None or target_node is None:
            return None
        source_type = str(source_node.get("type") or "unknown")
        target_type = str(target_node.get("type") or "unknown")
        relationship_type = str(edge.get("type") or "unknown")
        composite_key = f"{source_type}|{relationship_type}|{target_type}"
        return {
            "composite_key": composite_key,
            "instance": {
                "source_slug": str(
                    source_node.get("slug")
                    or source_node.get("domainId")
                    or source_node.get("id")
                    or ""
                ),
                "target_slug": str(
                    target_node.get("slug")
                    or target_node.get("domainId")
                    or target_node.get("id")
                    or ""
                ),
                "properties": _instance_properties(edge),
            },
        }

    sorted_edges = sorted(
        edges,
        key=lambda edge: (
            str(edge.get("type") or ""),
            str(edge.get("source") or ""),
            str(edge.get("target") or ""),
        ),
    )
    for edge in sorted_edges:
        parsed = _edge_instance(edge)
        if parsed is None:
            continue
        full_relationship_instances[parsed["composite_key"]].append(parsed["instance"])

    truncated_edges = sorted_edges[:limit]
    for edge in truncated_edges:
        parsed = _edge_instance(edge)
        if parsed is None:
            continue
        relationship_instances[parsed["composite_key"]].append(parsed["instance"])

    relationships: list[dict[str, Any]] = []
    if ontology is not None:
        for edge_type in ontology.edge_types:
            if not is_primary_relationship_for_display(edge_type):
                continue
            source_label = edge_type.source_labels[0] if edge_type.source_labels else ""
            target_label = edge_type.target_labels[0] if edge_type.target_labels else ""
            composite_key = f"{source_label}|{edge_type.label}|{target_label}"
            type_instances = relationship_instances.get(composite_key, [])
            if not type_instances:
                for key, instances in relationship_instances.items():
                    parts = key.split("|")
                    if len(parts) == 3 and parts[1] == edge_type.label:
                        composite_key = key
                        type_instances = instances
                        break
            reverse_label = _reverse_relationship_label(edge_type)
            total_instances = len(full_relationship_instances.get(composite_key, []))
            relationships.append(
                {
                    "key": composite_key,
                    "source_entity_type": source_label,
                    "target_entity_type": target_label,
                    "relationship_type": edge_type.label,
                    "reverse_relationship_type": reverse_label,
                    "reverse_relationship_description": (
                        f"Inverse of `{edge_type.label}`" if reverse_label else None
                    ),
                    "prepopulated_instances": edge_type.prepopulated,
                    "description": edge_type.description or None,
                    "instance_count": total_instances,
                    "instances_returned": len(type_instances),
                    "instances_truncated": total_instances > len(type_instances),
                    "instances": type_instances,
                    "required_parameters": list(edge_type.properties),
                    "optional_parameters": [],
                    "parameter_definitions": {
                        prop: prop.replace("_", " ").strip() or prop
                        for prop in edge_type.properties
                    },
                }
            )

    seen_relationship_keys = {row["key"] for row in relationships}
    for composite_key, type_instances in relationship_instances.items():
        if composite_key in seen_relationship_keys:
            continue
        parts = composite_key.split("|")
        if len(parts) != 3:
            continue
        relationship_label = parts[1]
        if any(
            is_secondary_bidirectional_edge(edge)
            for edge in (ontology.edge_types if ontology else ())
            if edge.label == relationship_label
        ):
            continue
        total_instances = len(full_relationship_instances.get(composite_key, []))
        relationships.append(
            {
                "key": composite_key,
                "source_entity_type": parts[0],
                "target_entity_type": parts[2],
                "relationship_type": parts[1],
                "reverse_relationship_type": None,
                "reverse_relationship_description": None,
                "prepopulated_instances": False,
                "description": None,
                "instance_count": total_instances,
                "instances_returned": len(type_instances),
                "instances_truncated": total_instances > len(type_instances),
                "instances": type_instances,
                "required_parameters": [],
                "optional_parameters": [],
                "parameter_definitions": {},
            }
        )

    return {
        "found": ontology is not None or bool(entities) or bool(relationships),
        "knowledge_graph_id": knowledge_graph_id,
        "entities": entities,
        "relationships": relationships,
        "counts": {
            "entity_types": len(entities),
            "relationship_types": len(relationships),
            "entity_instances": len(nodes),
            "relationship_instances": len(edges),
        },
        "limits": {
            "requested": limit,
            "entity_instances_returned": len(truncated_nodes),
            "relationship_instances_returned": len(truncated_edges),
            "entity_instances_truncated": len(nodes) > len(truncated_nodes),
            "relationship_instances_truncated": len(edges) > len(truncated_edges),
        },
    }
