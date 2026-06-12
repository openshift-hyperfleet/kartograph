"""Tests for relationship ownership rules in per-instance descriptions."""

from management.domain.extraction_relationship_authoring import (
    format_ignore_line,
    format_owned_line_prefix,
    per_instance_description_relationship_errors,
    relationship_authoring_guidance_for_entity_type,
    relationship_authoring_lines_for_entity_type,
)


def test_includes_relationship_when_entity_has_more_instances() -> None:
    lines = relationship_authoring_lines_for_entity_type(
        "Adapter",
        edge_types=[
            {"label": "deploys", "source_type": "Adapter", "target_type": "Cluster"},
        ],
        entity_instance_counts={"Adapter": 10, "Cluster": 3},
    )

    assert len(lines) == 1
    assert lines[0].relationship_label == "deploys"
    assert lines[0].counterpart_type == "Cluster"


def test_omits_relationship_when_entity_has_fewer_instances() -> None:
    lines = relationship_authoring_lines_for_entity_type(
        "Cluster",
        edge_types=[
            {"label": "deploys", "source_type": "Adapter", "target_type": "Cluster"},
        ],
        entity_instance_counts={"Adapter": 10, "Cluster": 3},
    )

    assert lines == ()


def test_omits_relationship_when_counts_are_equal() -> None:
    lines = relationship_authoring_lines_for_entity_type(
        "Adapter",
        edge_types=[
            {"label": "connects", "source_type": "Adapter", "target_type": "Service"},
        ],
        entity_instance_counts={"Adapter": 5, "Service": 5},
    )

    assert lines == ()


def test_adapter_omits_componenttest_relationship_but_keeps_resource() -> None:
    counts = {"Adapter": 19, "Resource": 9, "ComponentTest": 1264}
    edges = [
        {"label": "operates_on", "source_type": "Adapter", "target_type": "Resource"},
        {"label": "verifies", "source_type": "ComponentTest", "target_type": "Adapter"},
        {"label": "verifies_inverse", "source_type": "Adapter", "target_type": "ComponentTest"},
    ]
    guidance = relationship_authoring_guidance_for_entity_type(
        "Adapter",
        edge_types=edges,
        entity_instance_counts=counts,
    )
    owned = {(line.relationship_label, line.counterpart_type) for line in guidance.owned}
    ignored = {(line.relationship_label, line.counterpart_type) for line in guidance.ignored}

    assert ("operates_on", "Resource") in owned
    assert ("verifies_inverse", "ComponentTest") in ignored
    assert ("verifies", "ComponentTest") in ignored
    assert len(owned) == 1
    assert len(ignored) == 2


def test_includes_inbound_relationship_when_target_side_has_more_instances() -> None:
    lines = relationship_authoring_lines_for_entity_type(
        "Service",
        edge_types=[
            {"label": "exposes", "source_type": "Service", "target_type": "Route"},
        ],
        entity_instance_counts={"Service": 8, "Route": 2},
    )

    assert len(lines) == 1
    assert lines[0].entity_type == "Service"
    assert lines[0].counterpart_type == "Route"


def test_rejects_active_line_for_ignored_relationship() -> None:
    counts = {"Adapter": 19, "Resource": 9, "ComponentTest": 1264}
    edges = [
        {"label": "operates_on", "source_type": "Adapter", "target_type": "Resource"},
        {"label": "verifies_inverse", "source_type": "Adapter", "target_type": "ComponentTest"},
    ]
    description = """
For each Adapter instance, capture everything.

Properties:
- name: from source

Adapter -> operates_on -> Resource: link managed resources
Adapter -> verifies_inverse -> ComponentTest: link tests
"""
    errors = per_instance_description_relationship_errors(
        description,
        "Adapter",
        edge_types=edges,
        entity_instance_counts=counts,
    )

    assert any("verifies_inverse" in err and "must not" in err.lower() for err in errors)


def test_requires_ignore_line_for_counterpart_owned_edge() -> None:
    counts = {"Adapter": 19, "Resource": 9, "ComponentTest": 1264}
    edges = [
        {"label": "operates_on", "source_type": "Adapter", "target_type": "Resource"},
        {"label": "verifies_inverse", "source_type": "Adapter", "target_type": "ComponentTest"},
    ]
    description = """
Properties:
- name: from source

Adapter -> operates_on -> Resource: link managed resources
"""
    errors = per_instance_description_relationship_errors(
        description,
        "Adapter",
        edge_types=edges,
        entity_instance_counts=counts,
    )

    assert any("IGNORE" in err and "verifies_inverse" in err for err in errors)


def test_accepts_canonical_adapter_description() -> None:
    counts = {"Adapter": 19, "Resource": 9, "ComponentTest": 1264}
    edges = [
        {"label": "operates_on", "source_type": "Adapter", "target_type": "Resource"},
        {"label": "verifies_inverse", "source_type": "Adapter", "target_type": "ComponentTest"},
    ]
    description = f"""
Properties:
- name: from source

{format_owned_line_prefix(
    relationship_authoring_guidance_for_entity_type(
        "Adapter", edge_types=edges, entity_instance_counts=counts
    ).owned[0]
)} link managed resources

Ignore these relationships:
{format_ignore_line(
    relationship_authoring_guidance_for_entity_type(
        "Adapter", edge_types=edges, entity_instance_counts=counts
    ).ignored[0],
    entity_count=19,
    counterpart_count=1264,
)}
"""
    errors = per_instance_description_relationship_errors(
        description,
        "Adapter",
        edge_types=edges,
        entity_instance_counts=counts,
    )

    assert errors == ()
