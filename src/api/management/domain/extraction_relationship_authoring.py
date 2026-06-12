"""Rules for which relationship types belong in per-instance extraction descriptions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RelationshipAuthoringLine:
    """One relationship type an extraction job set should cover."""

    entity_type: str
    relationship_label: str
    counterpart_type: str


@dataclass(frozen=True)
class RelationshipAuthoringGuidance:
    """Owned vs ignored relationship lines for one entity type."""

    owned: tuple[RelationshipAuthoringLine, ...]
    ignored: tuple[RelationshipAuthoringLine, ...]


def format_owned_line_prefix(line: RelationshipAuthoringLine) -> str:
    return (
        f"{line.entity_type} -> {line.relationship_label} -> {line.counterpart_type}:"
    )


def format_ignore_line(
    line: RelationshipAuthoringLine,
    *,
    entity_count: int,
    counterpart_count: int,
) -> str:
    return (
        f"IGNORE {line.entity_type} -> {line.relationship_label} -> {line.counterpart_type}: "
        f"handled by {line.counterpart_type} job sets ({counterpart_count} vs "
        f"{line.entity_type} {entity_count} instances). Do not create or update this edge "
        f"in this job set."
    )


def edge_type_dicts_from_ontology(ontology: Any | None) -> list[dict[str, Any]]:
    """Normalize ontology edge types for relationship authoring helpers."""
    if ontology is None:
        return []
    edge_types = getattr(ontology, "edge_types", None) or []
    rows: list[dict[str, Any]] = []
    for edge in edge_types:
        source_labels = getattr(edge, "source_labels", None) or ()
        target_labels = getattr(edge, "target_labels", None) or ()
        rows.append(
            {
                "label": str(getattr(edge, "label", "") or "").strip(),
                "source_type": str(source_labels[0]).strip() if source_labels else "",
                "target_type": str(target_labels[0]).strip() if target_labels else "",
            }
        )
    return rows


def node_type_dicts_from_ontology(ontology: Any | None) -> list[dict[str, Any]]:
    """Normalize ontology node types for property authoring helpers."""
    if ontology is None:
        return []
    node_types = getattr(ontology, "node_types", None) or []
    rows: list[dict[str, Any]] = []
    for node in node_types:
        rows.append(
            {
                "label": str(getattr(node, "label", "") or "").strip(),
                "description": str(getattr(node, "description", "") or "").strip(),
                "required_properties": list(getattr(node, "required_properties", None) or ()),
                "optional_properties": list(getattr(node, "optional_properties", None) or ()),
            }
        )
    return rows


def properties_for_entity_type(
    entity_type: str,
    *,
    node_types: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Return all schema property names declared on one entity type."""
    for node in node_types:
        if str(node.get("label") or "").strip() != entity_type:
            continue
        required = tuple(str(name).strip() for name in node.get("required_properties") or () if str(name).strip())
        optional = tuple(str(name).strip() for name in node.get("optional_properties") or () if str(name).strip())
        return required + optional
    return ()


def entity_type_authoring_context(
    entity_type: str,
    *,
    node_types: list[dict[str, Any]],
    edge_types: list[dict[str, Any]],
    entity_instance_counts: dict[str, int],
) -> dict[str, Any]:
    """Schema-backed context for drafting one by_instances job set description."""
    properties = properties_for_entity_type(entity_type, node_types=node_types)
    relationship_payload = relationship_authoring_payload_for_entity_type(
        entity_type,
        edge_types=edge_types,
        entity_instance_counts=entity_instance_counts,
    )
    return {
        "entity_type": entity_type,
        "properties": list(properties),
        "relationship_authoring": relationship_payload,
    }


_RELATIONSHIP_LINE_RE = re.compile(
    r"^(?:IGNORE\s+)?(?P<entity>[^>]+?)\s*->\s*(?P<label>[^>]+?)\s*->\s*(?P<counterpart>[^:]+?)\s*:",
    re.IGNORECASE,
)


def _parse_relationship_lines(description: str) -> list[tuple[bool, str, str, str]]:
    """Return (is_ignore, entity_type, label, counterpart) tuples from description lines."""
    parsed: list[tuple[bool, str, str, str]] = []
    for raw_line in description.splitlines():
        stripped = raw_line.strip()
        if "->" not in stripped or ":" not in stripped:
            continue
        is_ignore = stripped.upper().startswith("IGNORE ")
        match = _RELATIONSHIP_LINE_RE.match(stripped)
        if match is None:
            continue
        parsed.append(
            (
                is_ignore,
                match.group("entity").strip(),
                match.group("label").strip(),
                match.group("counterpart").strip(),
            )
        )
    return parsed


def _valid_relationship_keys_for_entity(
    entity_type: str,
    *,
    edge_types: list[dict[str, Any]],
) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for line in _relationship_lines_involving_entity_type(entity_type, edge_types=edge_types):
        keys.add((line.entity_type, line.relationship_label, line.counterpart_type))
    return keys


def _property_names_from_description(description: str) -> set[str]:
    names: set[str] = set()
    in_properties = False
    for raw_line in description.splitlines():
        stripped = raw_line.strip()
        if stripped.lower().startswith("properties:"):
            in_properties = True
            continue
        if in_properties and "->" in stripped and ":" in stripped:
            in_properties = False
        if not in_properties:
            continue
        if stripped.startswith("- "):
            body = stripped[2:].strip()
            if ":" in body:
                names.add(body.split(":", 1)[0].strip())
    return names


def per_instance_description_property_errors(
    description: str,
    entity_type: str,
    *,
    node_types: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Validate Properties section names against ontology node type definitions."""
    if not node_types:
        return ()
    known = set(properties_for_entity_type(entity_type, node_types=node_types))
    if not known:
        return (f"{entity_type}: entity type not found in ontology.",)

    listed = _property_names_from_description(description)
    errors: list[str] = []
    unknown = sorted(name for name in listed if name not in known)
    for name in unknown:
        errors.append(
            f"{entity_type}: property '{name}' is not defined on this entity type in the ontology."
        )
    missing = sorted(name for name in known if name not in listed)
    for name in missing:
        errors.append(
            f"{entity_type}: missing property line '- {name}:' under Properties (required by schema)."
        )
    return tuple(errors)


def per_instance_description_unknown_relationship_errors(
    description: str,
    entity_type: str,
    *,
    edge_types: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Reject relationship lines that do not exist in the ontology for this entity type."""
    if not edge_types:
        return ()
    valid = _valid_relationship_keys_for_entity(entity_type, edge_types=edge_types)
    errors: list[str] = []
    for is_ignore, line_entity, label, counterpart in _parse_relationship_lines(description):
        if line_entity != entity_type:
            continue
        key = (line_entity, label, counterpart)
        if key not in valid:
            action = "IGNORE line" if is_ignore else "relationship line"
            errors.append(
                f"{entity_type}: {action} '{line_entity} -> {label} -> {counterpart}' "
                "is not a relationship type in the ontology for this entity type."
            )
    return tuple(errors)


def _relationship_lines_involving_entity_type(
    entity_type: str,
    *,
    edge_types: list[dict[str, Any]],
) -> tuple[RelationshipAuthoringLine, ...]:
    lines: list[RelationshipAuthoringLine] = []
    seen: set[tuple[str, str, str]] = set()

    for edge in edge_types:
        source_type = str(edge.get("source_type") or edge.get("sourceType") or "").strip()
        target_type = str(edge.get("target_type") or edge.get("targetType") or "").strip()
        label = str(edge.get("label") or edge.get("name") or edge.get("type") or "").strip()
        if not label:
            continue

        if source_type == entity_type and target_type:
            key = (entity_type, label, target_type)
            if key not in seen:
                seen.add(key)
                lines.append(
                    RelationshipAuthoringLine(
                        entity_type=entity_type,
                        relationship_label=label,
                        counterpart_type=target_type,
                    )
                )
            continue

        if target_type == entity_type and source_type:
            key = (entity_type, label, source_type)
            if key not in seen:
                seen.add(key)
                lines.append(
                    RelationshipAuthoringLine(
                        entity_type=entity_type,
                        relationship_label=label,
                        counterpart_type=source_type,
                    )
                )

    return tuple(sorted(lines, key=lambda line: (line.relationship_label, line.counterpart_type)))


def relationship_authoring_guidance_for_entity_type(
    entity_type: str,
    *,
    edge_types: list[dict[str, Any]],
    entity_instance_counts: dict[str, int],
) -> RelationshipAuthoringGuidance:
    """Split ontology edges into owned vs ignored lines for per-instance descriptions."""
    entity_count = entity_instance_counts.get(entity_type, 0)
    if entity_count <= 0:
        return RelationshipAuthoringGuidance(owned=(), ignored=())

    owned: list[RelationshipAuthoringLine] = []
    ignored: list[RelationshipAuthoringLine] = []
    for line in _relationship_lines_involving_entity_type(entity_type, edge_types=edge_types):
        counterpart_count = entity_instance_counts.get(line.counterpart_type, 0)
        if entity_count > counterpart_count:
            owned.append(line)
        else:
            ignored.append(line)

    return RelationshipAuthoringGuidance(owned=tuple(owned), ignored=tuple(ignored))


def relationship_authoring_lines_for_entity_type(
    entity_type: str,
    *,
    edge_types: list[dict[str, Any]],
    entity_instance_counts: dict[str, int],
) -> tuple[RelationshipAuthoringLine, ...]:
    """Return relationship lines EntityX jobs should cover to avoid duplicate work.

    When EntityX relates to EntityY, only the side with more live instances
    should create/update that relationship in its extraction jobs. The side
    with fewer (or equal) instances omits the line.
    """
    return relationship_authoring_guidance_for_entity_type(
        entity_type,
        edge_types=edge_types,
        entity_instance_counts=entity_instance_counts,
    ).owned


def _line_key(line: RelationshipAuthoringLine) -> str:
    return (
        f"{line.entity_type} -> {line.relationship_label} -> {line.counterpart_type}"
    )


def _active_relationship_line_present(description: str, line: RelationshipAuthoringLine) -> bool:
    key = _line_key(line).lower()
    for raw_line in description.splitlines():
        stripped = raw_line.strip()
        if stripped.upper().startswith("IGNORE "):
            continue
        if key in stripped.lower() and ":" in stripped:
            return True
    return False


def _ignore_relationship_line_present(description: str, line: RelationshipAuthoringLine) -> bool:
    key = _line_key(line).lower()
    for raw_line in description.splitlines():
        stripped = raw_line.strip()
        if not stripped.upper().startswith("IGNORE "):
            continue
        if key in stripped.lower():
            return True
    return False


def per_instance_description_relationship_errors(
    description: str,
    entity_type: str,
    *,
    edge_types: list[dict[str, Any]],
    entity_instance_counts: dict[str, int],
) -> tuple[str, ...]:
    """Validate owned vs IGNORE relationship lines in a per-instance description."""
    if not edge_types:
        return ()

    guidance = relationship_authoring_guidance_for_entity_type(
        entity_type,
        edge_types=edge_types,
        entity_instance_counts=entity_instance_counts,
    )
    errors: list[str] = []

    for line in guidance.owned:
        if not _active_relationship_line_present(description, line):
            errors.append(
                f"{entity_type}: missing owned relationship line "
                f"'{format_owned_line_prefix(line)}' (include extraction instructions after the colon)."
            )

    for line in guidance.ignored:
        if _active_relationship_line_present(description, line):
            errors.append(
                f"{entity_type}: must not list '{_line_key(line)}' as an active extraction target "
                f"(counterpart has more instances). Use an IGNORE line instead."
            )
        if not _ignore_relationship_line_present(description, line):
            errors.append(
                f"{entity_type}: missing IGNORE line for '{_line_key(line)}' under "
                "'Ignore these relationships:'."
            )

    return tuple(errors)


def relationship_authoring_by_entity_type(
    *,
    entity_instance_counts: dict[str, int],
    edge_types: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build owned/ignored guidance for every entity type in counts or ontology edges."""
    entity_types = sorted(
        {
            *entity_instance_counts.keys(),
            *(edge.get("source_type") or "" for edge in edge_types),
            *(edge.get("target_type") or "" for edge in edge_types),
        }
    )
    payload: dict[str, Any] = {}
    for entity_type in entity_types:
        if not entity_type:
            continue
        payload[entity_type] = relationship_authoring_payload_for_entity_type(
            entity_type,
            edge_types=edge_types,
            entity_instance_counts=entity_instance_counts,
        )
    return payload


def relationship_authoring_payload_for_entity_type(
    entity_type: str,
    *,
    edge_types: list[dict[str, Any]],
    entity_instance_counts: dict[str, int],
) -> dict[str, Any]:
    """Serialize owned/ignored lines for API responses and agent tooling."""
    entity_count = entity_instance_counts.get(entity_type, 0)
    guidance = relationship_authoring_guidance_for_entity_type(
        entity_type,
        edge_types=edge_types,
        entity_instance_counts=entity_instance_counts,
    )
    return {
        "entity_type": entity_type,
        "entity_instance_count": entity_count,
        "owned": [
            {
                "relationship_label": line.relationship_label,
                "counterpart_type": line.counterpart_type,
                "line_prefix": format_owned_line_prefix(line),
            }
            for line in guidance.owned
        ],
        "ignored": [
            {
                "relationship_label": line.relationship_label,
                "counterpart_type": line.counterpart_type,
                "ignore_line": format_ignore_line(
                    line,
                    entity_count=entity_count,
                    counterpart_count=entity_instance_counts.get(line.counterpart_type, 0),
                ),
            }
            for line in guidance.ignored
        ],
    }
