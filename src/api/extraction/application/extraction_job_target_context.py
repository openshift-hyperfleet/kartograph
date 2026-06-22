"""Enrich extraction job target instances with live graph context for agent workspaces."""

from __future__ import annotations

from typing import Any

from extraction.domain.extraction_job import ExtractionTargetInstance
from extraction.ports.workload_graph import WorkloadGraphNode

_PLATFORM_MANAGED_PROPERTIES = frozenset(
    {
        "data_source_id",
        "knowledge_graph_id",
        "graph_id",
        "source_path",
    }
)


def _properties_for_entity_type(
    entity_type: str,
    *,
    node_types: list[dict[str, Any]],
) -> tuple[str, ...]:
    for node in node_types:
        if str(node.get("label") or "").strip() != entity_type:
            continue
        required = tuple(
            str(name).strip()
            for name in node.get("required_properties") or ()
            if str(name).strip()
        )
        optional = tuple(
            str(name).strip()
            for name in node.get("optional_properties") or ()
            if str(name).strip()
        )
        return required + optional
    return ()


def _property_is_missing(properties: dict[str, Any], property_name: str) -> bool:
    value = properties.get(property_name)
    return value is None or value == ""


def missing_properties_for_instance(
    *,
    entity_type: str,
    node_properties: dict[str, Any],
    node_types: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Return ontology property names absent or empty on one live graph node."""
    missing: list[str] = []
    for property_name in _properties_for_entity_type(
        entity_type, node_types=node_types
    ):
        if property_name in _PLATFORM_MANAGED_PROPERTIES:
            continue
        if _property_is_missing(node_properties, property_name):
            missing.append(property_name)
    return tuple(sorted(missing))


def enrich_target_instance_for_context(
    instance: ExtractionTargetInstance,
    *,
    graph_node: WorkloadGraphNode | None,
    node_types: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build one job-context target entry with graph id and property gaps."""
    payload = instance.to_dict()
    if graph_node is None:
        payload["graph_id"] = None
        payload["properties_missing"] = list(
            _properties_for_entity_type(instance.entity_type, node_types=node_types)
        )
        return payload

    payload["graph_id"] = graph_node.id
    payload["properties_missing"] = list(
        missing_properties_for_instance(
            entity_type=instance.entity_type,
            node_properties=graph_node.properties,
            node_types=node_types,
        )
    )
    return payload


def enrich_target_instances_for_context(
    instances: tuple[ExtractionTargetInstance, ...],
    *,
    graph_nodes_by_slug: dict[str, WorkloadGraphNode],
    node_types: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build enriched target_instances payload for job-context.json."""
    return [
        enrich_target_instance_for_context(
            instance,
            graph_node=graph_nodes_by_slug.get(instance.slug),
            node_types=node_types,
        )
        for instance in instances
    ]
