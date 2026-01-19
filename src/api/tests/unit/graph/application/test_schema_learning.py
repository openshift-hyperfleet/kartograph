"""Unit tests for schema learning (optional property discovery)."""

from unittest.mock import create_autospec

import pytest

from graph.application.services.graph_mutation_service import GraphMutationService
from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
    TypeDefinition,
)
from graph.ports.repositories import IMutationApplier, ITypeDefinitionRepository


@pytest.fixture
def mock_applier():
    """Create mock mutation applier."""
    return create_autospec(IMutationApplier, instance=True)


@pytest.fixture
def mock_type_repo():
    """Create mock type definition repository."""
    return create_autospec(ITypeDefinitionRepository, instance=True)


@pytest.fixture
def service(mock_applier, mock_type_repo):
    """Create service with mocks."""
    from graph.domain.value_objects import MutationResult

    mock_applier.apply_batch.return_value = MutationResult(
        success=True, operations_applied=1
    )
    return GraphMutationService(
        mutation_applier=mock_applier, type_definition_repository=mock_type_repo
    )


class TestSchemaLearning:
    """Tests for automatic optional property discovery."""

    def test_extra_properties_added_to_optional(self, service, mock_type_repo):
        """Should add extra properties to type definition's optional_properties."""
        # DEFINE with required properties
        define_op = MutationOperation(
            op=MutationOperationType.DEFINE,
            type=EntityType.NODE,
            label="person",
            description="A person",
            required_properties={"slug", "name"},
        )

        # CREATE with extra properties beyond required
        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice",
                "name": "Alice",
                "email": "alice@example.com",  # Extra!
                "age": 30,  # Extra!
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        # Setup mock to return the type def after DEFINE is saved
        saved_type_def = None

        def mock_save(type_def):
            nonlocal saved_type_def
            saved_type_def = type_def

        def mock_get(label, entity_type):
            return saved_type_def

        mock_type_repo.save.side_effect = mock_save
        mock_type_repo.get.side_effect = mock_get

        service.apply_mutations([define_op, create_op])

        # Verify type definition was saved TWICE
        # First: from DEFINE (no optional props)
        # Second: merged with discovered optional props
        assert mock_type_repo.save.call_count == 2

        # Check the second save (merged)
        final_type_def = mock_type_repo.save.call_args_list[1][0][0]
        assert "age" in final_type_def.optional_properties
        assert "email" in final_type_def.optional_properties
        # data_source_id and source_path are system props, should be excluded
        assert "data_source_id" not in final_type_def.optional_properties
        assert "source_path" not in final_type_def.optional_properties

    def test_optional_properties_accumulate(self, service, mock_type_repo):
        """Should accumulate optional properties across multiple CREATEs."""
        # Existing type def with some optional props
        existing_type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name"},
            optional_properties={"email"},  # Already has email
        )
        mock_type_repo.get.return_value = existing_type_def

        # CREATE with different extra property
        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:def456abc123789a",
            label="person",
            set_properties={
                "slug": "bob",
                "name": "Bob",
                "phone": "+1234567890",  # New optional property!
                "data_source_id": "ds-123",
                "source_path": "people/bob.md",
            },
        )

        service.apply_mutations([create_op])

        # Should save updated type def with merged optional props
        mock_type_repo.save.assert_called_once()
        updated_type_def = mock_type_repo.save.call_args[0][0]
        assert "email" in updated_type_def.optional_properties  # Preserved
        assert "phone" in updated_type_def.optional_properties  # Added

    def test_system_properties_excluded_from_optional(self, service, mock_type_repo):
        """Should exclude system properties from optional properties."""
        existing_type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug"},
        )
        mock_type_repo.get.return_value = existing_type_def

        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice",
                "data_source_id": "ds-123",  # System prop - exclude
                "source_path": "people/alice.md",  # System prop - exclude
                "custom_field": "value",  # User prop - include
            },
        )

        service.apply_mutations([create_op])

        updated_type_def = mock_type_repo.save.call_args[0][0]
        assert "custom_field" in updated_type_def.optional_properties
        assert "data_source_id" not in updated_type_def.optional_properties
        assert "source_path" not in updated_type_def.optional_properties

    def test_no_update_when_no_extra_properties(self, service, mock_type_repo):
        """Should not update type def if no new optional properties."""
        existing_type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name"},
            optional_properties={"email"},
        )
        mock_type_repo.get.return_value = existing_type_def

        # CREATE with only required props + already-known optional prop
        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice",
                "name": "Alice",
                "email": "alice@example.com",  # Already in optional_properties
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        service.apply_mutations([create_op])

        # Should NOT save since no new optional properties discovered
        mock_type_repo.save.assert_not_called()

    def test_update_discovers_optional_properties(self, service, mock_type_repo):
        """UPDATE operations should trigger schema learning for new properties."""
        existing_type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name"},
            optional_properties={"email"},
        )
        mock_type_repo.get.return_value = existing_type_def

        # UPDATE with new property not in schema
        # NOTE: label is optional for UPDATE, but required for schema learning
        update_op = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",  # Include label for schema learning
            set_properties={
                "phone": "+1234567890",  # New optional property!
                "title": "Engineer",  # Another new one!
            },
        )

        service.apply_mutations([update_op])

        # Should save updated type def with new optional props
        mock_type_repo.save.assert_called_once()
        updated_type_def = mock_type_repo.save.call_args[0][0]
        assert "email" in updated_type_def.optional_properties  # Preserved
        assert "phone" in updated_type_def.optional_properties  # Added
        assert "title" in updated_type_def.optional_properties  # Added

    def test_update_without_label_skips_schema_learning(self, service, mock_type_repo):
        """UPDATE without label should skip schema learning (can't determine type)."""
        # UPDATE operations don't require label, but we need it for schema learning
        update_op = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            set_properties={"phone": "+1234567890"},
        )

        service.apply_mutations([update_op])

        # Should NOT attempt schema learning
        mock_type_repo.get.assert_not_called()
        mock_type_repo.save.assert_not_called()
