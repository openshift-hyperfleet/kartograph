"""Unit tests for TypeDefinition validation."""

import pytest
from pydantic import ValidationError

from graph.domain.value_objects import EntityType, TypeDefinition


class TestTypeDefinitionLabelValidation:
    """Tests for label validation."""

    def test_rejects_uppercase_label(self):
        """Should reject labels with uppercase characters."""
        with pytest.raises(ValidationError) as exc_info:
            TypeDefinition(
                label="Person",  # Uppercase - should be rejected!
                entity_type=EntityType.NODE,
                description="test",
                example_file_path="test.md",
                example_in_file_path="test",
                required_properties=set(),
            )

        error_str = str(exc_info.value).lower()
        assert "lowercase" in error_str

    def test_accepts_lowercase_label(self):
        """Should accept fully lowercase labels."""
        type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="test",
            example_file_path="test.md",
            example_in_file_path="test",
            required_properties=set(),
        )

        assert type_def.label == "person"

    def test_accepts_lowercase_with_underscores(self):
        """Should accept lowercase labels with underscores."""
        type_def = TypeDefinition(
            label="works_at",
            entity_type=EntityType.EDGE,
            description="test",
            example_file_path="test.md",
            example_in_file_path="test",
            required_properties=set(),
        )

        assert type_def.label == "works_at"
