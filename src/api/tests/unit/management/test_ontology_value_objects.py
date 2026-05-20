"""Unit tests for OntologyConfig, NodeTypeDefinition, EdgeTypeDefinition value objects."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
)


class TestNodeTypeDefinition:
    """Tests for NodeTypeDefinition value object."""

    def test_label_is_required_and_non_empty(self):
        """NodeTypeDefinition with empty label should raise ValueError."""
        with pytest.raises(ValueError, match="label"):
            NodeTypeDefinition(label="", description="")

    def test_label_whitespace_only_is_invalid(self):
        """NodeTypeDefinition with whitespace-only label should raise ValueError."""
        with pytest.raises(ValueError, match="label"):
            NodeTypeDefinition(label="   ", description="")

    def test_valid_minimal_node_type(self):
        """NodeTypeDefinition with only label should be valid."""
        nt = NodeTypeDefinition(label="Repository", description="")
        assert nt.label == "Repository"
        assert nt.description == ""
        assert nt.required_properties == ()
        assert nt.optional_properties == ()
        assert nt.prepopulated is False
        assert nt.prepopulated_instance_count == 0

    def test_required_properties_default_empty(self):
        """required_properties defaults to an empty tuple."""
        nt = NodeTypeDefinition(label="File", description="A file")
        assert nt.required_properties == ()

    def test_optional_properties_default_empty(self):
        """optional_properties defaults to an empty tuple."""
        nt = NodeTypeDefinition(label="File", description="A file")
        assert nt.optional_properties == ()

    def test_required_properties_stored_as_tuple(self):
        """required_properties should be stored as tuple regardless of input."""
        nt = NodeTypeDefinition(
            label="File",
            description="",
            required_properties=("name", "path"),
        )
        assert isinstance(nt.required_properties, tuple)
        assert nt.required_properties == ("name", "path")

    def test_optional_properties_stored_as_tuple(self):
        """optional_properties should be stored as tuple regardless of input."""
        nt = NodeTypeDefinition(
            label="File",
            description="",
            optional_properties=("size", "mime_type"),
        )
        assert isinstance(nt.optional_properties, tuple)
        assert nt.optional_properties == ("size", "mime_type")

    def test_equality_same_content(self):
        """Two NodeTypeDefinitions with same content should be equal."""
        nt1 = NodeTypeDefinition(
            label="Repo", description="A repo", required_properties=("url",)
        )
        nt2 = NodeTypeDefinition(
            label="Repo", description="A repo", required_properties=("url",)
        )
        assert nt1 == nt2

    def test_to_dict_round_trip(self):
        """to_dict() / from_dict() should round-trip correctly."""
        nt = NodeTypeDefinition(
            label="Commit",
            description="A git commit",
            required_properties=("sha", "message"),
            optional_properties=("author",),
        )
        d = nt.to_dict()
        restored = NodeTypeDefinition.from_dict(d)
        assert restored == nt

    def test_to_dict_contains_expected_keys(self):
        """to_dict() should contain label, description, required_properties, optional_properties."""
        nt = NodeTypeDefinition(label="Repo", description="desc")
        d = nt.to_dict()
        assert "label" in d
        assert "description" in d
        assert "required_properties" in d
        assert "optional_properties" in d
        assert "prepopulated" in d
        assert "prepopulated_instance_count" in d

    def test_prepopulated_instance_count_must_be_non_negative(self):
        """NodeTypeDefinition should reject negative prepopulated instance counts."""
        with pytest.raises(ValueError, match="prepopulated_instance_count"):
            NodeTypeDefinition(
                label="Repo",
                prepopulated=True,
                prepopulated_instance_count=-1,
            )


class TestEdgeTypeDefinition:
    """Tests for EdgeTypeDefinition value object."""

    def test_label_is_required_and_non_empty(self):
        """EdgeTypeDefinition with empty label should raise ValueError."""
        with pytest.raises(ValueError, match="label"):
            EdgeTypeDefinition(label="", description="")

    def test_label_whitespace_only_is_invalid(self):
        """EdgeTypeDefinition with whitespace-only label should raise ValueError."""
        with pytest.raises(ValueError, match="label"):
            EdgeTypeDefinition(label="  ", description="")

    def test_valid_minimal_edge_type(self):
        """EdgeTypeDefinition with only label should be valid."""
        et = EdgeTypeDefinition(label="CONTAINS", description="")
        assert et.label == "CONTAINS"
        assert et.description == ""
        assert et.source_labels == ()
        assert et.target_labels == ()
        assert et.properties == ()

    def test_source_labels_default_empty(self):
        """source_labels defaults to an empty tuple."""
        et = EdgeTypeDefinition(label="CONTAINS", description="")
        assert et.source_labels == ()

    def test_target_labels_default_empty(self):
        """target_labels defaults to an empty tuple."""
        et = EdgeTypeDefinition(label="CONTAINS", description="")
        assert et.target_labels == ()

    def test_properties_default_empty(self):
        """properties defaults to an empty tuple."""
        et = EdgeTypeDefinition(label="CONTAINS", description="")
        assert et.properties == ()

    def test_source_and_target_labels_stored_as_tuple(self):
        """source_labels and target_labels should be stored as tuples."""
        et = EdgeTypeDefinition(
            label="AUTHORED",
            description="",
            source_labels=("User",),
            target_labels=("Commit",),
        )
        assert isinstance(et.source_labels, tuple)
        assert isinstance(et.target_labels, tuple)
        assert et.source_labels == ("User",)
        assert et.target_labels == ("Commit",)

    def test_properties_stored_as_tuple(self):
        """properties should be stored as tuple."""
        et = EdgeTypeDefinition(
            label="CONTAINS",
            description="",
            properties=("weight",),
        )
        assert isinstance(et.properties, tuple)
        assert et.properties == ("weight",)

    def test_to_dict_round_trip(self):
        """to_dict() / from_dict() should round-trip correctly."""
        et = EdgeTypeDefinition(
            label="AUTHORED",
            description="User authored commit",
            source_labels=("User",),
            target_labels=("Commit",),
            properties=("date",),
        )
        d = et.to_dict()
        restored = EdgeTypeDefinition.from_dict(d)
        assert restored == et

    def test_to_dict_contains_expected_keys(self):
        """to_dict() should include all edge type fields."""
        et = EdgeTypeDefinition(label="CONTAINS", description="")
        d = et.to_dict()
        assert "label" in d
        assert "description" in d
        assert "source_labels" in d
        assert "target_labels" in d
        assert "properties" in d


class TestOntologyConfig:
    """Tests for OntologyConfig value object."""

    def test_empty_ontology_is_valid(self):
        """OntologyConfig with no types should be valid."""
        oc = OntologyConfig()
        assert oc.node_types == ()
        assert oc.edge_types == ()
        assert oc.approved_at is None

    def test_approved_at_defaults_to_none(self):
        """approved_at should default to None (unapproved ontology)."""
        oc = OntologyConfig()
        assert oc.approved_at is None

    def test_node_types_default_empty(self):
        """node_types should default to an empty tuple."""
        oc = OntologyConfig()
        assert oc.node_types == ()

    def test_edge_types_default_empty(self):
        """edge_types should default to an empty tuple."""
        oc = OntologyConfig()
        assert oc.edge_types == ()

    def test_with_node_types(self):
        """OntologyConfig can hold node types."""
        nt = NodeTypeDefinition(label="Repository", description="A repo")
        oc = OntologyConfig(node_types=(nt,))
        assert len(oc.node_types) == 1
        assert oc.node_types[0].label == "Repository"

    def test_with_edge_types(self):
        """OntologyConfig can hold edge types."""
        et = EdgeTypeDefinition(label="CONTAINS", description="")
        oc = OntologyConfig(edge_types=(et,))
        assert len(oc.edge_types) == 1
        assert oc.edge_types[0].label == "CONTAINS"

    def test_with_approved_at(self):
        """OntologyConfig can have an approved_at timestamp."""
        now = datetime.now(UTC)
        oc = OntologyConfig(approved_at=now)
        assert oc.approved_at == now

    def test_to_dict_round_trip_empty(self):
        """Empty OntologyConfig should round-trip through to_dict/from_dict."""
        oc = OntologyConfig()
        d = oc.to_dict()
        restored = OntologyConfig.from_dict(d)
        assert restored.node_types == ()
        assert restored.edge_types == ()
        assert restored.approved_at is None

    def test_to_dict_round_trip_with_types(self):
        """OntologyConfig with types should round-trip correctly."""
        nt = NodeTypeDefinition(
            label="Repository",
            description="A GitHub repository",
            required_properties=("url",),
            optional_properties=("description",),
        )
        et = EdgeTypeDefinition(
            label="CONTAINS",
            description="Containment edge",
            source_labels=("Repository",),
            target_labels=("File",),
        )
        now = datetime.now(UTC)
        oc = OntologyConfig(node_types=(nt,), edge_types=(et,), approved_at=now)
        d = oc.to_dict()
        restored = OntologyConfig.from_dict(d)
        assert len(restored.node_types) == 1
        assert restored.node_types[0].label == "Repository"
        assert restored.node_types[0].required_properties == ("url",)
        assert restored.node_types[0].optional_properties == ("description",)
        assert len(restored.edge_types) == 1
        assert restored.edge_types[0].label == "CONTAINS"
        assert restored.edge_types[0].source_labels == ("Repository",)
        # Timestamps may lose sub-microsecond precision; compare at second resolution
        assert restored.approved_at is not None
        assert abs((restored.approved_at - now).total_seconds()) < 1.0

    def test_to_dict_approved_at_none_serializes_as_none(self):
        """to_dict() with approved_at=None should serialize as None."""
        oc = OntologyConfig()
        d = oc.to_dict()
        assert d["approved_at"] is None

    def test_from_dict_with_null_approved_at(self):
        """from_dict() with approved_at=None should produce approved_at=None."""
        d = {"node_types": [], "edge_types": [], "approved_at": None}
        oc = OntologyConfig.from_dict(d)
        assert oc.approved_at is None

    def test_from_dict_with_iso_approved_at(self):
        """from_dict() with ISO-8601 approved_at string should parse correctly."""
        d = {
            "node_types": [],
            "edge_types": [],
            "approved_at": "2026-05-03T12:00:00+00:00",
        }
        oc = OntologyConfig.from_dict(d)
        assert oc.approved_at is not None
        assert oc.approved_at.year == 2026

    def test_to_dict_contains_expected_keys(self):
        """to_dict() should contain node_types, edge_types, approved_at."""
        oc = OntologyConfig()
        d = oc.to_dict()
        assert "node_types" in d
        assert "edge_types" in d
        assert "approved_at" in d

    def test_equality_same_content(self):
        """Two OntologyConfigs with same content should be equal."""
        nt = NodeTypeDefinition(label="Repo", description="")
        oc1 = OntologyConfig(node_types=(nt,))
        oc2 = OntologyConfig(node_types=(nt,))
        assert oc1 == oc2

    def test_node_types_stored_as_tuple(self):
        """node_types should be stored as a tuple."""
        nt = NodeTypeDefinition(label="Repo", description="")
        oc = OntologyConfig(node_types=(nt,))
        assert isinstance(oc.node_types, tuple)

    def test_edge_types_stored_as_tuple(self):
        """edge_types should be stored as a tuple."""
        et = EdgeTypeDefinition(label="CONTAINS", description="")
        oc = OntologyConfig(edge_types=(et,))
        assert isinstance(oc.edge_types, tuple)
