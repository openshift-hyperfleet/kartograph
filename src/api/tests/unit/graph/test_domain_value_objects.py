"""Unit tests for Graph domain value objects."""

import json

import pytest
from pydantic import ValidationError

from graph.domain.value_objects import (
    EdgeRecord,
    MutationLine,
    MutationOperation,
    NodeRecord,
)


class TestNodeRecord:
    """Tests for NodeRecord value object."""

    def test_creates_with_required_fields(self):
        """NodeRecord should create with id, label, and properties."""
        node = NodeRecord(
            id="node:abc123",
            label="Person",
            properties={"name": "Alice", "age": 30},
        )
        assert node.id == "node:abc123"
        assert node.label == "Person"
        assert node.properties == {"name": "Alice", "age": 30}

    def test_is_immutable(self):
        """NodeRecord should be immutable (frozen)."""
        node = NodeRecord(id="node:1", label="Test", properties={})
        with pytest.raises(ValidationError):
            node.id = "node:2"

    def test_requires_id(self):
        """NodeRecord should require id field."""
        with pytest.raises(ValidationError):
            NodeRecord(label="Test", properties={})

    def test_requires_label(self):
        """NodeRecord should require label field."""
        with pytest.raises(ValidationError):
            NodeRecord(id="node:1", properties={})

    def test_properties_default_to_empty_dict(self):
        """NodeRecord properties should default to empty dict."""
        node = NodeRecord(id="node:1", label="Test")
        assert node.properties == {}

    def test_equality_based_on_values(self):
        """NodeRecords with same values should be equal."""
        node1 = NodeRecord(id="node:1", label="Test", properties={"a": 1})
        node2 = NodeRecord(id="node:1", label="Test", properties={"a": 1})
        assert node1 == node2

    def test_inequality_when_different(self):
        """NodeRecords with different values should not be equal."""
        node1 = NodeRecord(id="node:1", label="Test", properties={})
        node2 = NodeRecord(id="node:2", label="Test", properties={})
        assert node1 != node2


class TestEdgeRecord:
    """Tests for EdgeRecord value object."""

    def test_creates_with_required_fields(self):
        """EdgeRecord should create with all required fields."""
        edge = EdgeRecord(
            id="edge:xyz789",
            label="KNOWS",
            start_id="node:abc",
            end_id="node:def",
            properties={"since": 2020},
        )
        assert edge.id == "edge:xyz789"
        assert edge.label == "KNOWS"
        assert edge.start_id == "node:abc"
        assert edge.end_id == "node:def"
        assert edge.properties == {"since": 2020}

    def test_is_immutable(self):
        """EdgeRecord should be immutable (frozen)."""
        edge = EdgeRecord(
            id="edge:1",
            label="REL",
            start_id="a",
            end_id="b",
            properties={},
        )
        with pytest.raises(ValidationError):
            edge.label = "NEW_REL"

    def test_requires_start_and_end_ids(self):
        """EdgeRecord should require start_id and end_id."""
        with pytest.raises(ValidationError):
            EdgeRecord(id="edge:1", label="REL", properties={})

    def test_properties_default_to_empty_dict(self):
        """EdgeRecord properties should default to empty dict."""
        edge = EdgeRecord(
            id="edge:1",
            label="REL",
            start_id="a",
            end_id="b",
        )
        assert edge.properties == {}

    def test_equality_based_on_values(self):
        """EdgeRecords with same values should be equal."""
        edge1 = EdgeRecord(
            id="edge:1", label="REL", start_id="a", end_id="b", properties={}
        )
        edge2 = EdgeRecord(
            id="edge:1", label="REL", start_id="a", end_id="b", properties={}
        )
        assert edge1 == edge2


class TestMutationOperation:
    """Tests for MutationOperation enum."""

    def test_has_create_operation(self):
        """Should have CREATE operation."""
        assert MutationOperation.CREATE.value == "CREATE"

    def test_has_update_operation(self):
        """Should have UPDATE operation."""
        assert MutationOperation.UPDATE.value == "UPDATE"

    def test_has_delete_operation(self):
        """Should have DELETE operation."""
        assert MutationOperation.DELETE.value == "DELETE"


class TestMutationLine:
    """Tests for MutationLine value object."""

    def test_create_operation(self):
        """MutationLine should support CREATE operation."""
        mutation = MutationLine(
            operation=MutationOperation.CREATE,
            id="person:alice123",
            data={"name": "Alice", "source_path": "people/alice.md"},
        )
        assert mutation.operation == MutationOperation.CREATE
        assert mutation.id == "person:alice123"
        assert mutation.data["name"] == "Alice"

    def test_update_operation(self):
        """MutationLine should support UPDATE operation."""
        mutation = MutationLine(
            operation=MutationOperation.UPDATE,
            id="person:bob456",
            data={"source_path": "people/robert.md"},
        )
        assert mutation.operation == MutationOperation.UPDATE

    def test_delete_operation(self):
        """MutationLine should support DELETE operation."""
        mutation = MutationLine(
            operation=MutationOperation.DELETE,
            id="person:charlie789",
        )
        assert mutation.operation == MutationOperation.DELETE
        assert mutation.data is None

    def test_is_immutable(self):
        """MutationLine should be immutable (frozen)."""
        mutation = MutationLine(
            operation=MutationOperation.CREATE,
            id="test:1",
            data={},
        )
        with pytest.raises(ValidationError):
            mutation.id = "test:2"

    def test_to_jsonl(self):
        """MutationLine should serialize to JSONL format."""
        mutation = MutationLine(
            operation=MutationOperation.CREATE,
            id="person:alice123",
            data={"name": "Alice"},
        )
        jsonl = mutation.to_jsonl()
        parsed = json.loads(jsonl)

        assert parsed["op"] == "CREATE"
        assert parsed["id"] == "person:alice123"
        assert parsed["data"] == {"name": "Alice"}

    def test_to_jsonl_without_data(self):
        """MutationLine DELETE should serialize without data field."""
        mutation = MutationLine(
            operation=MutationOperation.DELETE,
            id="person:bob456",
        )
        jsonl = mutation.to_jsonl()
        parsed = json.loads(jsonl)

        assert parsed["op"] == "DELETE"
        assert parsed["id"] == "person:bob456"
        assert "data" not in parsed

    def test_from_jsonl(self):
        """MutationLine should deserialize from JSONL format."""
        jsonl = '{"op": "UPDATE", "id": "person:charlie", "data": {"age": 30}}'
        mutation = MutationLine.from_jsonl(jsonl)

        assert mutation.operation == MutationOperation.UPDATE
        assert mutation.id == "person:charlie"
        assert mutation.data == {"age": 30}

    def test_roundtrip_serialization(self):
        """MutationLine should survive roundtrip serialization."""
        original = MutationLine(
            operation=MutationOperation.CREATE,
            id="test:roundtrip",
            data={"key": "value", "nested": {"a": 1}},
        )
        jsonl = original.to_jsonl()
        restored = MutationLine.from_jsonl(jsonl)

        assert restored == original
