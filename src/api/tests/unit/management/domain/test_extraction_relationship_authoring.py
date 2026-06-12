"""Tests for relationship ownership rules in per-instance descriptions."""

from management.domain.extraction_relationship_authoring import (
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
