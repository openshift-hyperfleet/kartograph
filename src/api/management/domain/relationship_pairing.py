"""Bidirectional relationship pairing for ontology authoring and edge instances."""

from __future__ import annotations

import hashlib
from typing import Any

from management.domain.value_objects import EdgeTypeDefinition, OntologyConfig

_INVERSE_LABEL_MAP: dict[str, str] = {
    "contains": "contained_in",
    "defines": "defined_by",
    "implements": "implemented_by",
    "covers": "covered_by",
    "owns": "owned_by",
    "uses": "used_by",
}


class RelationshipPairingError(ValueError):
    """Raised when bidirectional pairing metadata is inconsistent."""


def derive_inverse_label(primary_label: str) -> str:
    """Derive a default inverse edge label from the primary label."""
    normalized = primary_label.strip().lower()
    return _INVERSE_LABEL_MAP.get(normalized, f"{normalized}_inverse")


def bidirectional_pair_key(*, source_label: str, relationship_label: str, target_label: str) -> str:
    """Stable identifier for a directed relationship type in design artifacts."""
    return f"{source_label}|{relationship_label}|{target_label}"


def resolve_inverse_label_for_primary(edge_type: EdgeTypeDefinition) -> str:
    """Return the inverse label for a primary bidirectional edge type."""
    if edge_type.inverse_label:
        return edge_type.inverse_label.strip().lower()
    return derive_inverse_label(edge_type.label)


def build_inverse_edge_type(primary: EdgeTypeDefinition) -> EdgeTypeDefinition:
    """Build the auto-generated inverse edge type for a primary relationship."""
    if not primary.source_labels or not primary.target_labels:
        raise RelationshipPairingError(
            f"Relationship type `{primary.label}` requires source_labels and target_labels "
            "for bidirectional pairing"
        )
    inverse_label = resolve_inverse_label_for_primary(primary)
    source = primary.source_labels[0]
    target = primary.target_labels[0]
    description = (
        f"Inverse of `{primary.label}` ({target} → {source}); auto-generated for bidirectional pairing."
    )
    return EdgeTypeDefinition(
        label=inverse_label,
        description=description,
        source_labels=(target,),
        target_labels=(source,),
        properties=primary.properties,
        prepopulated=primary.prepopulated,
        prepopulated_instance_count=0,
        instance_generator=primary.instance_generator,
        bidirectional=True,
        inverse_of=primary.label,
        auto_generated=True,
        bidirectional_pair_key=bidirectional_pair_key(
            source_label=target,
            relationship_label=inverse_label,
            target_label=source,
        ),
    )


def _is_primary_bidirectional_edge(edge_type: EdgeTypeDefinition) -> bool:
    return edge_type.bidirectional and not edge_type.auto_generated and not edge_type.inverse_of


def expand_ontology_bidirectional_pairs(config: OntologyConfig) -> OntologyConfig:
    """Ensure every primary bidirectional edge type has a linked inverse type definition."""
    edge_types = list(config.edge_types)
    by_label = {edge.label: edge for edge in edge_types}

    for primary in list(edge_types):
        if not _is_primary_bidirectional_edge(primary):
            continue
        if not primary.source_labels or not primary.target_labels:
            raise RelationshipPairingError(
                f"Relationship type `{primary.label}` cannot be bidirectional without "
                "source_labels and target_labels"
            )

        inverse_label = resolve_inverse_label_for_primary(primary)
        source = primary.source_labels[0]
        target = primary.target_labels[0]
        pair_key = bidirectional_pair_key(
            source_label=source,
            relationship_label=primary.label,
            target_label=target,
        )

        existing_inverse = by_label.get(inverse_label)
        if existing_inverse is not None:
            if existing_inverse.inverse_of and existing_inverse.inverse_of != primary.label:
                raise RelationshipPairingError(
                    f"inverse_label `{inverse_label}` already exists and is paired with "
                    f"`{existing_inverse.inverse_of}`, not `{primary.label}`"
                )
            continue

        inverse = build_inverse_edge_type(primary)
        edge_types.append(inverse)
        by_label[inverse.label] = inverse

        # Rebuild primary with pairing metadata (frozen dataclass)
        index = edge_types.index(primary)
        edge_types[index] = EdgeTypeDefinition(
            label=primary.label,
            description=primary.description,
            source_labels=primary.source_labels,
            target_labels=primary.target_labels,
            properties=primary.properties,
            prepopulated=primary.prepopulated,
            prepopulated_instance_count=primary.prepopulated_instance_count,
            instance_generator=primary.instance_generator,
            bidirectional=True,
            inverse_label=inverse_label,
            auto_generated=False,
            inverse_of=None,
            bidirectional_pair_key=pair_key,
        )
        by_label[primary.label] = edge_types[index]

    return OntologyConfig(
        node_types=config.node_types,
        edge_types=tuple(edge_types),
        approved_at=config.approved_at,
    )


def deterministic_twin_edge_id(
    *,
    relationship_label: str,
    start_id: str,
    end_id: str,
    tenant_id: str = "",
) -> str:
    """Match json_relationships_to_jsonl deterministic edge id rules."""
    normalized_label = relationship_label.strip().lower()
    combined = f"{tenant_id}:{start_id.strip()}:{normalized_label}:{end_id.strip()}"
    digest = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f"{normalized_label}:{digest}"


def _primary_edge_by_label(ontology: OntologyConfig) -> dict[str, EdgeTypeDefinition]:
    return {
        edge.label: edge
        for edge in ontology.edge_types
        if _is_primary_bidirectional_edge(edge)
    }


def normalize_authoring_edge_type_dicts(edge_types: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Default bidirectional=true for newly authored primary relationship types."""
    normalized: list[dict[str, Any]] = []
    for row in edge_types:
        payload = dict(row)
        if (
            "bidirectional" not in payload
            and not payload.get("auto_generated")
            and not payload.get("inverse_of")
        ):
            payload["bidirectional"] = True
        normalized.append(payload)
    return normalized


def expand_twin_edge_creates(
    operations: list[dict[str, Any]],
    *,
    ontology: OntologyConfig,
    tenant_id: str,
) -> list[dict[str, Any]]:
    """Append inverse edge CREATE operations for bidirectional relationship types."""
    primary_edges = _primary_edge_by_label(ontology)
    if not primary_edges:
        return list(operations)

    expanded: list[dict[str, Any]] = []
    for operation in operations:
        expanded.append(operation)
        if operation.get("op") != "CREATE" or operation.get("type") != "edge":
            continue

        label = str(operation.get("label") or "").strip().lower()
        primary = primary_edges.get(label)
        if primary is None:
            continue

        start_id = str(operation.get("start_id") or "").strip()
        end_id = str(operation.get("end_id") or "").strip()
        if not start_id or not end_id:
            continue

        inverse_label = resolve_inverse_label_for_primary(primary)
        properties = dict(operation.get("set_properties") or {})
        twin = {
            "op": "CREATE",
            "type": "edge",
            "id": deterministic_twin_edge_id(
                relationship_label=inverse_label,
                start_id=end_id,
                end_id=start_id,
                tenant_id=tenant_id,
            ),
            "label": inverse_label,
            "start_id": end_id,
            "end_id": start_id,
            "set_properties": properties,
        }
        expanded.append(twin)

    return expanded


def ontology_config_from_authoring_payload(data: dict[str, Any]) -> OntologyConfig:
    """Build OntologyConfig from API/workload payload with authoring defaults."""
    payload = dict(data)
    payload["edge_types"] = normalize_authoring_edge_type_dicts(
        list(payload.get("edge_types") or [])
    )
    return OntologyConfig.from_dict(payload)


def twin_validation_errors(
    *,
    ontology: OntologyConfig,
    relationship_counts: dict[str, int],
) -> list[str]:
    """Report primary/inverse relationship instance count mismatches."""
    errors: list[str] = []
    for primary in ontology.edge_types:
        if not _is_primary_bidirectional_edge(primary):
            continue
        if not primary.source_labels or not primary.target_labels:
            continue
        source = primary.source_labels[0]
        target = primary.target_labels[0]
        primary_key = bidirectional_pair_key(
            source_label=source,
            relationship_label=primary.label,
            target_label=target,
        )
        inverse_label = resolve_inverse_label_for_primary(primary)
        inverse_key = bidirectional_pair_key(
            source_label=target,
            relationship_label=inverse_label,
            target_label=source,
        )
        primary_count = relationship_counts.get(primary_key, 0)
        inverse_count = relationship_counts.get(inverse_key, 0)
        if primary_count != inverse_count:
            errors.append(
                f"Bidirectional pair `{primary.label}` / `{inverse_label}` is unbalanced: "
                f"primary={primary_count}, inverse={inverse_count}"
            )
    return errors
