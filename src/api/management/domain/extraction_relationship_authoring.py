"""Rules for which relationship types belong in per-instance extraction descriptions."""

from __future__ import annotations

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
