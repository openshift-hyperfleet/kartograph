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
    entity_count = entity_instance_counts.get(entity_type, 0)
    if entity_count <= 0:
        return ()

    lines: list[RelationshipAuthoringLine] = []
    seen: set[tuple[str, str, str]] = set()

    for edge in edge_types:
        source_type = str(edge.get("source_type") or edge.get("sourceType") or "").strip()
        target_type = str(edge.get("target_type") or edge.get("targetType") or "").strip()
        label = str(edge.get("label") or edge.get("name") or edge.get("type") or "").strip()
        if not label:
            continue

        if source_type == entity_type and target_type:
            counterpart = target_type
            counterpart_count = entity_instance_counts.get(counterpart, 0)
            if entity_count > counterpart_count:
                key = (entity_type, label, counterpart)
                if key not in seen:
                    seen.add(key)
                    lines.append(
                        RelationshipAuthoringLine(
                            entity_type=entity_type,
                            relationship_label=label,
                            counterpart_type=counterpart,
                        )
                    )
            continue

        if target_type == entity_type and source_type:
            counterpart = source_type
            counterpart_count = entity_instance_counts.get(counterpart, 0)
            if entity_count > counterpart_count:
                key = (entity_type, label, counterpart)
                if key not in seen:
                    seen.add(key)
                    lines.append(
                        RelationshipAuthoringLine(
                            entity_type=entity_type,
                            relationship_label=label,
                            counterpart_type=counterpart,
                        )
                    )

    return tuple(sorted(lines, key=lambda line: (line.relationship_label, line.counterpart_type)))
