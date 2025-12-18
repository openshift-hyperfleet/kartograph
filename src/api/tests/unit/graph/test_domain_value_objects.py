"""Unit tests for Graph domain value objects."""

import pytest
from pydantic import ValidationError

from graph.domain.value_objects import (
    EntityType,
    MutationOperationType,
    EdgeRecord,
    MutationOperation,
    MutationResult,
    NodeRecord,
    TypeDefinition,
)


class TestNodeRecord:
    """Tests for NodeRecord value object."""

    def test_creates_with_required_fields(self):
        """NodeRecord should create with id, label, and properties."""
        node = NodeRecord(
            id="node:abc123",
            label="person",
            properties={"name": "Alice", "age": 30},
        )
        assert node.id == "node:abc123"
        assert node.label == "person"
        assert node.properties == {"name": "Alice", "age": 30}

    def test_is_immutable(self):
        """NodeRecord should be immutable (frozen)."""
        node = NodeRecord(id="node:1", label="test", properties={})
        with pytest.raises(ValidationError):
            node.id = "node:2"

    def test_requires_id(self):
        """NodeRecord should require id field."""
        with pytest.raises(ValidationError):
            NodeRecord(label="test", properties={})

    def test_requires_label(self):
        """NodeRecord should require label field."""
        with pytest.raises(ValidationError):
            NodeRecord(id="node:1", properties={})

    def test_properties_default_to_empty_dict(self):
        """NodeRecord properties should default to empty dict."""
        node = NodeRecord(id="node:1", label="test")
        assert node.properties == {}

    def test_equality_based_on_values(self):
        """NodeRecords with same values should be equal."""
        node1 = NodeRecord(id="node:1", label="test", properties={"a": 1})
        node2 = NodeRecord(id="node:1", label="test", properties={"a": 1})
        assert node1 == node2

    def test_inequality_when_different(self):
        """NodeRecords with different values should not be equal."""
        node1 = NodeRecord(id="node:1", label="test", properties={})
        node2 = NodeRecord(id="node:2", label="test", properties={})
        assert node1 != node2


class TestEdgeRecord:
    """Tests for EdgeRecord value object."""

    def test_creates_with_required_fields(self):
        """EdgeRecord should create with all required fields."""
        edge = EdgeRecord(
            id="edge:xyz789",
            label="knows",
            start_id="node:abc",
            end_id="node:def",
            properties={"since": 2020},
        )
        assert edge.id == "edge:xyz789"
        assert edge.label == "knows"
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


class TestTypeDefinition:
    """Tests for TypeDefinition value object."""

    def test_creates_with_all_fields(self):
        """TypeDefinition should create with all required fields."""
        type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person entity",
            example_file_path="people/alice.md",
            example_in_file_path="# Alice Smith",
            required_properties={"slug", "name"},
            optional_properties={"email", "github"},
        )
        assert type_def.label == "person"
        assert type_def.entity_type == "node"
        assert type_def.required_properties == {"slug", "name"}
        assert type_def.optional_properties == {"email", "github"}

    def test_is_immutable(self):
        """TypeDefinition should be immutable (frozen)."""
        type_def = TypeDefinition(
            label="test",
            entity_type=EntityType.NODE,
            description="Test",
            example_file_path="test.md",
            example_in_file_path="test",
            required_properties=[],
        )
        with pytest.raises(ValidationError):
            type_def.label = "Changed"


class TestMutationOperation:
    """Tests for MutationOperation value object."""

    # --- DEFINE operation tests ---

    def test_define_node_valid(self):
        """DEFINE node operation should validate with all required fields."""
        mutation = MutationOperation(
            op=MutationOperationType.DEFINE,
            type="node",
            id="person:def0000000000000",
            label="person",
            description="A person entity",
            example_file_path="people/alice.md",
            example_in_file_path="# Alice",
            required_properties=["slug", "name"],
            optional_properties=["email"],
        )
        mutation.validate_operation()  # Should not raise

    def test_define_requires_label(self):
        """DEFINE should require label."""
        mutation = MutationOperation(
            op=MutationOperationType.DEFINE,
            type="node",
            id="test:def1111111111111",
            description="Test",
            example_file_path="test.md",
            example_in_file_path="test",
            required_properties=[],
        )
        with pytest.raises(ValueError, match="DEFINE requires 'label'"):
            mutation.validate_operation()

    def test_define_requires_description(self):
        """DEFINE should require description."""
        mutation = MutationOperation(
            op=MutationOperationType.DEFINE,
            type="node",
            id="test:def2222222222222",
            label="test",
            example_file_path="test.md",
            example_in_file_path="test",
            required_properties=[],
        )
        with pytest.raises(ValueError, match="DEFINE requires"):
            mutation.validate_operation()

    def test_define_cannot_have_set_properties(self):
        """DEFINE should not allow set_properties."""
        mutation = MutationOperation(
            op=MutationOperationType.DEFINE,
            type="node",
            id="test:def3333333333333",
            label="test",
            description="Test",
            example_file_path="test.md",
            example_in_file_path="test",
            required_properties=[],
            set_properties={"foo": "bar"},
        )
        with pytest.raises(ValueError, match="DEFINE cannot include"):
            mutation.validate_operation()

    def test_to_type_definition(self):
        """DEFINE operation should convert to TypeDefinition."""
        mutation = MutationOperation(
            op=MutationOperationType.DEFINE,
            type="node",
            id="person:def4444444444444",
            label="person",
            description="A person",
            example_file_path="people/alice.md",
            example_in_file_path="# Alice",
            required_properties=["slug"],
            optional_properties=["email"],
        )
        type_def = mutation.to_type_definition()

        assert type_def.label == "person"
        assert type_def.entity_type == "node"
        assert type_def.description == "A person"
        assert type_def.required_properties == {"slug"}
        assert type_def.optional_properties == {"email"}

    def test_to_type_definition_only_for_define(self):
        """Only DEFINE operations can convert to TypeDefinition."""
        mutation = MutationOperation(
            op=MutationOperationType.DELETE,
            type="node",
            id="person:abc123def456789a",
        )
        with pytest.raises(ValueError, match="Only DEFINE operations"):
            mutation.to_type_definition()

    # --- CREATE operation tests ---

    def test_create_node_valid(self):
        """CREATE node operation should validate with all required fields."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type="node",
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice-smith",
                "name": "Alice",
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )
        mutation.validate_operation()  # Should not raise

    def test_create_edge_valid(self):
        """CREATE edge operation should validate with all required fields."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type="edge",
            id="knows:abc123def456789a",
            label="knows",
            start_id="person:abc123def456789a",
            end_id="person:def456abc123789a",
            set_properties={
                "since": 2020,
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )
        mutation.validate_operation()  # Should not raise

    def test_create_requires_label(self):
        """CREATE should require label."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type="node",
            id="person:abc123def456789a",
            set_properties={
                "slug": "alice",
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )
        with pytest.raises(ValueError, match="CREATE requires 'label'"):
            mutation.validate_operation()

    def test_create_requires_set_properties(self):
        """CREATE should require set_properties."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type="node",
            id="person:abc123def456789a",
            label="person",
        )
        with pytest.raises(ValueError, match="CREATE requires 'set_properties'"):
            mutation.validate_operation()

    def test_create_requires_data_source_id(self):
        """CREATE should require data_source_id in set_properties."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type="node",
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice",
                "source_path": "people/alice.md",
            },
        )
        with pytest.raises(ValueError, match="data_source_id"):
            mutation.validate_operation()

    def test_create_requires_source_path(self):
        """CREATE should require source_path in set_properties."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type="node",
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice",
                "data_source_id": "ds-123",
            },
        )
        with pytest.raises(ValueError, match="source_path"):
            mutation.validate_operation()

    def test_create_node_requires_slug(self):
        """CREATE node should require slug in set_properties."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type="node",
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )
        with pytest.raises(ValueError, match="slug"):
            mutation.validate_operation()

    def test_create_edge_requires_start_and_end_id(self):
        """CREATE edge should require start_id and end_id."""
        mutation = MutationOperation(
            op=MutationOperationType.CREATE,
            type="edge",
            id="knows:abc123def456789a",
            label="knows",
            set_properties={
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )
        with pytest.raises(ValueError, match="start_id.*end_id"):
            mutation.validate_operation()

    # --- UPDATE operation tests ---

    def test_update_with_set_properties(self):
        """UPDATE with set_properties should validate."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type="node",
            id="person:abc123def456789a",
            set_properties={"name": "Alice Updated"},
        )
        mutation.validate_operation()  # Should not raise

    def test_update_with_remove_properties(self):
        """UPDATE with remove_properties should validate."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type="node",
            id="person:abc123def456789a",
            remove_properties=["middle_name"],
        )
        mutation.validate_operation()  # Should not raise

    def test_update_with_both_set_and_remove(self):
        """UPDATE with both set and remove properties should validate."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type="node",
            id="person:abc123def456789a",
            set_properties={"name": "Alice"},
            remove_properties=["nickname"],
        )
        mutation.validate_operation()  # Should not raise

    def test_update_requires_set_or_remove(self):
        """UPDATE should require at least set_properties or remove_properties."""
        mutation = MutationOperation(
            op=MutationOperationType.UPDATE,
            type="node",
            id="person:abc123def456789a",
        )
        with pytest.raises(ValueError, match="UPDATE requires at least one"):
            mutation.validate_operation()

    # --- DELETE operation tests ---

    def test_delete_valid(self):
        """DELETE operation should validate with only op, type, and id."""
        mutation = MutationOperation(
            op=MutationOperationType.DELETE,
            type="node",
            id="person:abc123def456789a",
        )
        mutation.validate_operation()  # Should not raise

    def test_delete_cannot_have_set_properties(self):
        """DELETE should not allow set_properties."""
        mutation = MutationOperation(
            op=MutationOperationType.DELETE,
            type="node",
            id="person:abc123def456789a",
            set_properties={"foo": "bar"},
        )
        with pytest.raises(ValueError, match="DELETE only requires"):
            mutation.validate_operation()

    def test_delete_cannot_have_label(self):
        """DELETE should not allow label."""
        mutation = MutationOperation(
            op=MutationOperationType.DELETE,
            type="node",
            id="person:abc123def456789a",
            label="person",
        )
        with pytest.raises(ValueError, match="DELETE only requires"):
            mutation.validate_operation()

    # --- ID pattern validation tests ---

    def test_id_pattern_validation(self):
        """ID should match pattern {type}:{16_hex_chars}."""
        with pytest.raises(ValidationError):
            MutationOperation(
                op=MutationOperationType.DELETE,
                type="node",
                id="invalid_id_format",
            )

    def test_id_accepts_valid_pattern(self):
        """ID should accept valid {type}:{16_hex_chars} pattern."""
        mutation = MutationOperation(
            op=MutationOperationType.DELETE,
            type="node",
            id="person:abc123def456789a",
        )
        assert mutation.id == "person:abc123def456789a"


class TestMutationResult:
    """Tests for MutationResult value object."""

    def test_success_result(self):
        """MutationResult should represent successful operations."""
        result = MutationResult(
            success=True,
            operations_applied=5,
        )
        assert result.success is True
        assert result.operations_applied == 5
        assert result.errors == []

    def test_failure_result(self):
        """MutationResult should represent failed operations with errors."""
        result = MutationResult(
            success=False,
            operations_applied=0,
            errors=["Invalid operation", "Database connection failed"],
        )
        assert result.success is False
        assert result.operations_applied == 0
        assert len(result.errors) == 2

    def test_is_immutable(self):
        """MutationResult should be immutable (frozen)."""
        result = MutationResult(success=True, operations_applied=1)
        with pytest.raises(ValidationError):
            result.success = False
