"""Unit tests for bidirectional relationship pairing."""

from __future__ import annotations


from management.domain.relationship_pairing import (
    derive_inverse_label,
    expand_ontology_bidirectional_pairs,
    expand_twin_edge_creates,
)
from management.domain.value_objects import EdgeTypeDefinition, OntologyConfig


class TestDeriveInverseLabel:
    def test_contains_maps_to_contained_in(self) -> None:
        assert derive_inverse_label("contains") == "contained_in"

    def test_defines_maps_to_defined_by(self) -> None:
        assert derive_inverse_label("defines") == "defined_by"

    def test_unknown_uses_suffix(self) -> None:
        assert derive_inverse_label("relates_to") == "relates_to_inverse"


class TestExpandOntologyBidirectionalPairs:
    def test_auto_generates_inverse_type(self) -> None:
        config = OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="contains",
                    description="Repository contains test",
                    source_labels=("repository",),
                    target_labels=("test",),
                    bidirectional=True,
                ),
            )
        )

        expanded = expand_ontology_bidirectional_pairs(config)

        labels = {edge.label for edge in expanded.edge_types}
        assert labels == {"contains", "contained_in"}
        inverse = next(edge for edge in expanded.edge_types if edge.label == "contained_in")
        assert inverse.source_labels == ("test",)
        assert inverse.target_labels == ("repository",)
        assert inverse.inverse_of == "contains"
        assert inverse.auto_generated is True

    def test_skips_when_bidirectional_false(self) -> None:
        config = OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="depends_on",
                    source_labels=("service",),
                    target_labels=("service",),
                    bidirectional=False,
                ),
            )
        )

        expanded = expand_ontology_bidirectional_pairs(config)

        assert len(expanded.edge_types) == 1
        assert expanded.edge_types[0].label == "depends_on"

    def test_respects_explicit_inverse_label(self) -> None:
        config = OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="contains",
                    source_labels=("repository",),
                    target_labels=("test",),
                    bidirectional=True,
                    inverse_label="housed_in",
                ),
            )
        )

        expanded = expand_ontology_bidirectional_pairs(config)
        inverse = next(edge for edge in expanded.edge_types if edge.label == "housed_in")

        assert inverse.inverse_of == "contains"

    def test_legacy_edge_without_bidirectional_flag_is_unchanged(self) -> None:
        config = OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="contains",
                    source_labels=("repository",),
                    target_labels=("test",),
                ),
            )
        )

        expanded = expand_ontology_bidirectional_pairs(config)

        assert len(expanded.edge_types) == 1

    def test_dedupe_drops_manual_inverse_before_expanding(self) -> None:
        config = OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="exercises",
                    source_labels=("ComponentTest",),
                    target_labels=("APIEndpoint",),
                    bidirectional=True,
                    inverse_label="exercises_inverse",
                ),
                EdgeTypeDefinition(
                    label="exercises_inverse",
                    source_labels=("APIEndpoint",),
                    target_labels=("ComponentTest",),
                    bidirectional=True,
                ),
            )
        )

        expanded = expand_ontology_bidirectional_pairs(config)

        inverse_rows = [edge for edge in expanded.edge_types if edge.label == "exercises_inverse"]
        assert len(inverse_rows) == 1
        assert inverse_rows[0].auto_generated is True
        assert inverse_rows[0].inverse_of == "exercises"


class TestExpandTwinEdgeCreates:
    def test_primary_create_expands_to_inverse(self) -> None:
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
        operations = [
            {
                "op": "CREATE",
                "type": "edge",
                "id": "contains:0123456789abcdef",
                "label": "contains",
                "start_id": "repository:aaaaaaaaaaaaaaaa",
                "end_id": "test:bbbbbbbbbbbbbbbb",
                "set_properties": {
                    "data_source_id": "ds-1",
                    "source_path": "bootstrap",
                    "knowledge_graph_id": "kg-1",
                },
            }
        ]

        expanded = expand_twin_edge_creates(
            operations,
            ontology=ontology,
            tenant_id="tenant-1",
        )

        assert len(expanded) == 2
        inverse = expanded[1]
        assert inverse["label"] == "contained_in"
        assert inverse["start_id"] == "test:bbbbbbbbbbbbbbbb"
        assert inverse["end_id"] == "repository:aaaaaaaaaaaaaaaa"

    def test_non_bidirectional_edge_is_unchanged(self) -> None:
        ontology = OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="depends_on",
                    source_labels=("service",),
                    target_labels=("service",),
                    bidirectional=False,
                ),
            )
        )
        operations = [
            {
                "op": "CREATE",
                "type": "edge",
                "id": "depends_on:0123456789abcdef",
                "label": "depends_on",
                "start_id": "service:aaaaaaaaaaaaaaaa",
                "end_id": "service:bbbbbbbbbbbbbbbb",
                "set_properties": {
                    "data_source_id": "ds-1",
                    "source_path": "bootstrap",
                    "knowledge_graph_id": "kg-1",
                },
            }
        ]

        expanded = expand_twin_edge_creates(
            operations,
            ontology=ontology,
            tenant_id="tenant-1",
        )

        assert len(expanded) == 1
