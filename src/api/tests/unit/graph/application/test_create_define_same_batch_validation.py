"""Tests for CREATE validation against DEFINE in same batch."""

from unittest.mock import Mock


from graph.application.services.graph_mutation_service import GraphMutationService
from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
    MutationResult,
)


class TestCreateDefineValidationInBatch:
    """Tests that CREATE operations are validated with system properties included."""

    def test_rejects_create_missing_system_properties(self):
        """Should reject CREATE missing system properties even if DEFINE is in same batch."""
        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_repo = Mock()
        mock_type_repo.get.return_value = None  # No existing type def

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_repo,
        )

        # DEFINE without system props (user only specifies user props)
        define_op = MutationOperation(
            op=MutationOperationType.DEFINE,
            type=EntityType.NODE,
            label="person",
            description="A person",
            required_properties={"name"},  # User only specifies "name"
        )

        # CREATE missing slug (node system property)
        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "name": "Alice",
                # Missing slug! (system property)
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        result = service.apply_mutations([define_op, create_op])

        # Should fail validation
        assert result.success is False
        assert any("slug" in error.lower() for error in result.errors)

    def test_accepts_create_with_all_system_properties(self):
        """Should accept CREATE with all system properties present."""
        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_repo = Mock()
        mock_type_repo.get.return_value = None

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_repo,
        )

        define_op = MutationOperation(
            op=MutationOperationType.DEFINE,
            type=EntityType.NODE,
            label="person",
            description="A person",
            required_properties={"name"},
        )

        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "name": "Alice",
                "slug": "alice",  # System property present!
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        result = service.apply_mutations([define_op, create_op])

        assert result.success is True

    def test_edge_does_not_require_slug(self):
        """Edge CREATE should not require slug (node-specific system property)."""
        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_repo = Mock()
        mock_type_repo.get.return_value = None

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_repo,
        )

        define_op = MutationOperation(
            op=MutationOperationType.DEFINE,
            type=EntityType.EDGE,
            label="knows",
            description="Knows relationship",
            required_properties={"since"},
        )

        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.EDGE,
            id="knows:abc123def456789a",
            label="knows",
            start_id="person:aaa111bbb222ccc3",
            end_id="person:def456abc123789a",
            set_properties={
                "since": 2020,
                # No slug required for edges!
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        result = service.apply_mutations([define_op, create_op])

        assert result.success is True
