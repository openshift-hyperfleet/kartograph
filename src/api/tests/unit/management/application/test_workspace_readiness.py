"""Unit tests for workspace readiness evaluation."""

from __future__ import annotations

from management.application.workspace_readiness import (
    evaluate_workspace_readiness,
    prepopulated_gaps_from_live_counts,
)
from management.domain.value_objects import EdgeTypeDefinition, NodeTypeDefinition, OntologyConfig


def test_evaluate_workspace_readiness_flags_missing_prepopulated_entity_types() -> None:
    config = OntologyConfig(
        node_types=(
            NodeTypeDefinition(label="service", prepopulated=True, prepopulated_instance_count=0),
            NodeTypeDefinition(label="team"),
        ),
        edge_types=(
            EdgeTypeDefinition(
                label="owns",
                source_labels=("team",),
                target_labels=("service",),
            ),
        ),
    )

    readiness = evaluate_workspace_readiness(config)

    assert readiness.has_minimum_entity_types is True
    assert readiness.has_minimum_relationship_types is True
    assert readiness.prepopulated_types_ready is False
    assert readiness.prepopulated_types_without_instances == ("service",)
    assert any("service" in reason for reason in readiness.blocking_reasons)


def test_prepopulated_gaps_from_live_counts_uses_graph_counts() -> None:
    config = OntologyConfig(
        node_types=(
            NodeTypeDefinition(label="folder", prepopulated=True),
            NodeTypeDefinition(label="file", prepopulated=True),
        ),
        edge_types=(
            EdgeTypeDefinition(
                label="contains",
                source_labels=("folder",),
                target_labels=("file",),
                prepopulated=True,
            ),
        ),
    )

    gaps = prepopulated_gaps_from_live_counts(
        config,
        entity_instance_counts={"folder": 3, "file": 0},
        relationship_instance_counts={"folder|contains|file": 0},
    )

    assert gaps["entity_types_without_instances"] == ("file",)
    assert gaps["relationship_types_without_instances"] == ("folder|contains|file",)
