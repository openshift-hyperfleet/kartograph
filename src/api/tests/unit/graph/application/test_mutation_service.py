"""Unit tests for GraphMutationService application service."""

from unittest.mock import Mock

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
    MutationResult,
    TypeDefinition,
)


class TestGraphMutationServiceApplyMutations:
    """Tests for apply_mutations method."""

    def test_apply_mutations_delegates_to_applier(self):
        """Should delegate mutation operations to the MutationApplier."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=2,
        )
        mock_type_def_repo = Mock()
        # Mock type definition for Person
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            example_file_path="people/alice.md",
            example_in_file_path="alice",
            required_properties={"slug", "name"},
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                set_properties={"email": "alice@example.com"},
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations(operations)

        # Should call applier with operations
        mock_applier.apply_batch.assert_called_once_with(operations)

        # Should return result from applier
        assert result.success is True
        assert result.operations_applied == 2

    def test_apply_mutations_stores_define_operations(self):
        """Should store DEFINE operations in TypeDefinitionRepository."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=1,
        )
        mock_type_def_repo = Mock()

        operations = [
            MutationOperation(
                op=MutationOperationType.DEFINE,
                type=EntityType.NODE,
                label="person",
                description="A person in the organization",
                example_file_path="people/alice.md",
                example_in_file_path="alice",
                required_properties={"slug", "name"},
                optional_properties={"email"},
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        service.apply_mutations(operations)

        # Should save TypeDefinition to repository
        mock_type_def_repo.save.assert_called_once()
        saved_type_def = mock_type_def_repo.save.call_args[0][0]
        assert saved_type_def.label == "person"
        assert saved_type_def.entity_type == "node"
        assert saved_type_def.description == "A person in the organization"

    def test_apply_mutations_emits_probe_events(self):
        """Should emit probe events for successful mutations."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=1,
        )
        mock_type_def_repo = Mock()
        # Mock type definition for Person
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            example_file_path="people/alice.md",
            example_in_file_path="alice",
            required_properties={"slug", "name"},
        )
        mock_probe = Mock()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
            probe=mock_probe,
        )
        service.apply_mutations(operations)

        # Should emit probe event
        mock_probe.mutations_applied.assert_called_once_with(
            operations_applied=1,
            success=True,
        )

    def test_apply_mutations_emits_failure_probe_events(self):
        """Should emit probe events for failed mutations."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=False,
            operations_applied=0,
            errors=["Database error"],
        )
        mock_type_def_repo = Mock()
        mock_probe = Mock()

        operations = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
            probe=mock_probe,
        )
        service.apply_mutations(operations)

        # Should emit failure probe event
        mock_probe.mutations_applied.assert_called_once_with(
            operations_applied=0,
            success=False,
        )

    def test_apply_empty_mutations_list(self):
        """Should handle empty mutations list gracefully."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=0,
        )
        mock_type_def_repo = Mock()

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations([])

        assert result.success is True
        assert result.operations_applied == 0

    def test_rejects_create_without_define_in_batch(self):
        """Should reject CREATE operations without corresponding DEFINE in batch."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_type_def_repo = Mock()
        mock_type_def_repo.get.return_value = None  # Type not defined

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations(operations)

        # Should fail validation
        assert result.success is False
        assert result.operations_applied == 0
        assert len(result.errors) > 0
        assert "person" in result.errors[0]
        assert "not defined" in result.errors[0].lower()

        # Should not call applier
        mock_applier.apply_batch.assert_not_called()

    def test_accepts_create_with_define_in_batch(self):
        """Should accept CREATE when DEFINE is in same batch."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=2,
        )
        mock_type_def_repo = Mock()
        mock_type_def_repo.get.return_value = None  # Not in repo yet

        operations = [
            MutationOperation(
                op=MutationOperationType.DEFINE,
                type=EntityType.NODE,
                label="person",
                description="A person",
                example_file_path="people/alice.md",
                example_in_file_path="alice",
                required_properties={"slug", "name"},
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations(operations)

        # Should succeed
        assert result.success is True
        assert result.operations_applied == 2

        # Should call applier
        mock_applier.apply_batch.assert_called_once()

    def test_accepts_create_with_define_in_repository(self):
        """Should accept CREATE when type is already defined in repository."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=1,
        )
        mock_type_def_repo = Mock()
        # Type already exists in repository
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            example_file_path="people/alice.md",
            example_in_file_path="alice",
            required_properties={"slug", "name"},
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations(operations)

        # Should succeed
        assert result.success is True
        assert result.operations_applied == 1

        # Should call applier
        mock_applier.apply_batch.assert_called_once()

    def test_rejects_create_missing_required_properties(self):
        """Should reject CREATE when required properties are missing."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_type_def_repo = Mock()
        # Type exists with required properties
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            example_file_path="people/alice.md",
            example_in_file_path="alice",
            required_properties={"slug", "name", "email"},  # email is required
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    # Missing required "email" property
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations(operations)

        # Should fail validation
        assert result.success is False
        assert result.operations_applied == 0
        assert len(result.errors) > 0
        assert "email" in result.errors[0]
        assert "required" in result.errors[0].lower()

        # Should not call applier
        mock_applier.apply_batch.assert_not_called()

    def test_accepts_create_with_all_required_properties(self):
        """Should accept CREATE when all required properties are present."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=1,
        )
        mock_type_def_repo = Mock()
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            example_file_path="people/alice.md",
            example_in_file_path="alice",
            required_properties={"slug", "name"},
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "email": "alice@example.com",  # Optional property
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations(operations)

        # Should succeed
        assert result.success is True
        assert result.operations_applied == 1


class TestGraphMutationServiceApplyFromJSONL:
    """Tests for apply_mutations_from_jsonl method."""

    def test_parses_jsonl_and_applies_mutations(self):
        """Should parse JSONL string and apply mutations."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=2,
        )
        mock_type_def_repo = Mock()
        # Mock type definition for Person
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            example_file_path="people/alice.md",
            example_in_file_path="alice",
            required_properties={"slug", "name"},
        )

        jsonl_content = """{"op":"CREATE","type":"node","id":"person:abc123def456789a","label":"person","set_properties":{"slug":"alice","name":"Alice","data_source_id":"ds-123","source_path":"people/alice.md"}}
{"op":"UPDATE","type":"node","id":"person:abc123def456789a","set_properties":{"email":"alice@example.com"}}"""

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations_from_jsonl(jsonl_content)

        # Should parse and apply 2 operations
        mock_applier.apply_batch.assert_called_once()
        operations = mock_applier.apply_batch.call_args[0][0]
        assert len(operations) == 2
        assert operations[0].op == MutationOperationType.CREATE
        assert operations[1].op == "UPDATE"

        # Should return result
        assert result.success is True
        assert result.operations_applied == 2

    def test_handles_empty_jsonl(self):
        """Should handle empty JSONL string."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=0,
        )
        mock_type_def_repo = Mock()

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations_from_jsonl("")

        # Should call apply with empty list
        mock_applier.apply_batch.assert_called_once_with([])
        assert result.success is True
        assert result.operations_applied == 0

    def test_handles_whitespace_only_lines(self):
        """Should ignore whitespace-only lines in JSONL."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True,
            operations_applied=1,
        )
        mock_type_def_repo = Mock()
        # Mock type definition for Person
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            example_file_path="people/alice.md",
            example_in_file_path="alice",
            required_properties={"slug", "name"},
        )

        jsonl_content = """
{"op":"CREATE","type":"node","id":"person:abc123def456789a","label":"person","set_properties":{"slug":"alice","name":"Alice","data_source_id":"ds-123","source_path":"people/alice.md"}}

"""

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        service.apply_mutations_from_jsonl(jsonl_content)

        # Should parse only the valid line
        operations = mock_applier.apply_batch.call_args[0][0]
        assert len(operations) == 1
        assert operations[0].op == MutationOperationType.CREATE

    def test_returns_error_on_invalid_json(self):
        """Should return error result for invalid JSON."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_type_def_repo = Mock()

        jsonl_content = """{"op":"CREATE","type":"node" INVALID JSON"""

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations_from_jsonl(jsonl_content)

        # Should return failure result
        assert result.success is False
        assert result.operations_applied == 0
        assert len(result.errors) > 0
        assert "JSON" in result.errors[0] or "parse" in result.errors[0].lower()

    def test_returns_error_on_invalid_mutation_operation(self):
        """Should return error result for invalid MutationOperation."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_type_def_repo = Mock()

        # Missing required 'op' field
        jsonl_content = """{"type":"node","id":"person:abc123def456789a"}"""

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations_from_jsonl(jsonl_content)

        # Should return failure result
        assert result.success is False
        assert result.operations_applied == 0
        assert len(result.errors) > 0
