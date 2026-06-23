"""Unit tests for bidirectional metadata in design artifacts."""

from __future__ import annotations

from management.application.design_artifacts import build_design_artifacts
from management.domain.relationship_pairing import expand_ontology_bidirectional_pairs
from management.domain.value_objects import EdgeTypeDefinition, OntologyConfig


def test_design_artifacts_exposes_reverse_relationship_type() -> None:
    ontology = expand_ontology_bidirectional_pairs(
        OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="contains",
                    source_labels=("repository",),
                    target_labels=("test",),
                    bidirectional=True,
                ),
            )
        )
    )

    artifacts = build_design_artifacts(
        knowledge_graph_id="kg-1",
        ontology=ontology,
        graph_data={"nodes": [], "edges": []},
        limit=100,
    )

    contains = next(
        row
        for row in artifacts["relationships"]
        if row["relationship_type"] == "contains"
    )
    assert contains["reverse_relationship_type"] == "contained_in"
    inverse_labels = {row["relationship_type"] for row in artifacts["relationships"]}
    assert "contained_in" not in inverse_labels
    assert len(artifacts["relationships"]) == 1


def test_design_artifacts_hides_auto_generated_inverse_rows() -> None:
    ontology = expand_ontology_bidirectional_pairs(
        OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="exercises",
                    source_labels=("ComponentTest",),
                    target_labels=("APIEndpoint",),
                    bidirectional=True,
                    inverse_label="exercises_inverse",
                ),
                EdgeTypeDefinition(
                    label="covered_by",
                    source_labels=("Feature",),
                    target_labels=("ComponentTest",),
                    bidirectional=True,
                ),
            )
        )
    )

    artifacts = build_design_artifacts(
        knowledge_graph_id="kg-1",
        ontology=ontology,
        graph_data={"nodes": [], "edges": []},
        limit=100,
    )

    labels = {row["relationship_type"] for row in artifacts["relationships"]}
    assert labels == {"exercises", "covered_by"}
    exercises = next(
        row
        for row in artifacts["relationships"]
        if row["relationship_type"] == "exercises"
    )
    assert exercises["reverse_relationship_type"] == "exercises_inverse"
