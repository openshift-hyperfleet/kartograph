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
                # Deliberately omit "slug" from caller-provided properties.
                # The assertion below only proves injection if "slug" is absent here.
                required_properties={"name"},
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
        assert saved_type_def.entity_type == EntityType.NODE
        assert saved_type_def.description == "A person in the organization"

        # System properties must be automatically added to required_properties
        # per spec: system properties (data_source_id, source_path, slug) are
        # automatically added to required properties for node types.
        # Because "slug" was NOT in the caller-provided set, this assertion only
        # passes when the service actually injects it — a regression would fail here.
        assert "data_source_id" in saved_type_def.required_properties
        assert "source_path" in saved_type_def.required_properties
        assert "slug" in saved_type_def.required_properties

    def test_apply_define_edge_type_adds_edge_system_properties(self):
        """DEFINE for edge type adds data_source_id and source_path but NOT slug.

        Spec (DEFINE edge type scenario): system properties for edges
        (data_source_id, source_path) are automatically added. slug is a node-only
        system property and MUST NOT appear in edge type definitions.
        """
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
                type=EntityType.EDGE,
                label="depends_on",
                description="Dependency relationship between components",
                required_properties={"weight"},
                optional_properties=set(),
            ),
        ]

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        service.apply_mutations(operations)

        mock_type_def_repo.save.assert_called_once()
        saved_type_def = mock_type_def_repo.save.call_args[0][0]
        assert saved_type_def.label == "depends_on"
        assert saved_type_def.entity_type == EntityType.EDGE
        assert (
            saved_type_def.description == "Dependency relationship between components"
        )

        # Edge system properties MUST be automatically added
        assert "data_source_id" in saved_type_def.required_properties
        assert "source_path" in saved_type_def.required_properties

        # slug is a node-only system property — MUST NOT appear on edge types
        assert "slug" not in saved_type_def.required_properties

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
        assert operations[1].op == MutationOperationType.UPDATE

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
        """Should return error result for invalid JSON with line number and content preview.

        Spec: 'the error is reported with the line number and a content preview'.
        """
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

        # Error message must include both parse indicator and the line number.
        # Use case-insensitive checks that are robust to message formatting.
        import re

        first_error = result.errors[0]
        assert "JSON" in first_error or "parse" in first_error.lower(), (
            f"Error message must mention JSON or parse, got: {first_error!r}"
        )
        assert re.search(r"\bline\s*1\b", first_error, re.IGNORECASE), (
            f"Error message must include 'line 1' token, got: {first_error!r}"
        )

        # At least one error entry must provide the content preview.
        # Order-agnostic check so it works even if more errors are added.
        assert len(result.errors) >= 2, (
            "Expected at least two error entries (parse error + content preview)"
        )
        assert any("line content" in err.lower() for err in result.errors), (
            "At least one error entry must include 'Line content:' preview"
        )

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


class TestKnowledgeGraphIdStamping:
    """Tests for knowledge_graph_id stamping behavior in GraphMutationService.

    The system stamps knowledge_graph_id on all CREATE and UPDATE operations,
    ensuring callers cannot spoof the graph ID.
    """

    def test_stamps_knowledge_graph_id_on_create_operation(self):
        """Service should stamp knowledge_graph_id on CREATE operations."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_def_repo = Mock()
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name"},
        )

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
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
                    # No knowledge_graph_id - service should stamp it
                },
            ),
        ]

        service.apply_mutations(operations, knowledge_graph_id="kg-123")

        # The applier should receive ops with knowledge_graph_id stamped
        mock_applier.apply_batch.assert_called_once()
        applied_ops = mock_applier.apply_batch.call_args[0][0]
        assert len(applied_ops) == 1
        assert applied_ops[0].set_properties is not None
        assert applied_ops[0].set_properties.get("knowledge_graph_id") == "kg-123"

    def test_overwrites_caller_provided_knowledge_graph_id(self):
        """Service should overwrite any caller-provided knowledge_graph_id."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_def_repo = Mock()
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name"},
        )

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
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
                    "knowledge_graph_id": "SPOOFED-ID",  # Caller tries to spoof!
                },
            ),
        ]

        service.apply_mutations(operations, knowledge_graph_id="kg-123")

        # The applier should receive ops with CORRECT knowledge_graph_id
        applied_ops = mock_applier.apply_batch.call_args[0][0]
        assert applied_ops[0].set_properties.get("knowledge_graph_id") == "kg-123"
        assert applied_ops[0].set_properties.get("knowledge_graph_id") != "SPOOFED-ID"

    def test_stamps_knowledge_graph_id_on_update_operation(self):
        """Service should stamp knowledge_graph_id on UPDATE operations with set_properties."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_def_repo = Mock()

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                set_properties={"name": "Alice Updated"},
            ),
        ]

        service.apply_mutations(operations, knowledge_graph_id="kg-456")

        # UPDATE with set_properties should also be stamped
        applied_ops = mock_applier.apply_batch.call_args[0][0]
        assert applied_ops[0].set_properties.get("knowledge_graph_id") == "kg-456"

    def test_does_not_stamp_on_delete_operation(self):
        """Service should NOT stamp knowledge_graph_id on DELETE operations."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_def_repo = Mock()

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
            ),
        ]

        service.apply_mutations(operations, knowledge_graph_id="kg-123")

        # DELETE ops have no set_properties - stamping should not apply
        applied_ops = mock_applier.apply_batch.call_args[0][0]
        assert applied_ops[0].set_properties is None

    def test_does_not_stamp_when_knowledge_graph_id_not_provided(self):
        """Service should not inject knowledge_graph_id into CREATE/UPDATE when param is omitted.

        Uses an UPDATE op with set_properties (no knowledge_graph_id) so the code
        path that stamps CREATE/UPDATE is actually reachable. The assertion verifies
        that knowledge_graph_id is absent from the applied operation — which would
        only be true if the service correctly skips stamping when the param is None.
        """
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_def_repo = Mock()
        # Prevent schema learning from interfering (no type def → skip)
        mock_type_def_repo.get.return_value = None

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )

        operations = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:abc123def456789a",
                # set_properties WITHOUT knowledge_graph_id — the service must
                # not inject it when apply_mutations() is called without the param.
                set_properties={
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            ),
        ]

        # No knowledge_graph_id provided — stamping must NOT occur
        service.apply_mutations(operations)

        # Verify the applier received the operation without knowledge_graph_id injected
        mock_applier.apply_batch.assert_called_once()
        applied_ops = mock_applier.apply_batch.call_args[0][0]
        assert "knowledge_graph_id" not in applied_ops[0].set_properties

    def test_stamps_knowledge_graph_id_in_jsonl_parse(self):
        """apply_mutations_from_jsonl should stamp knowledge_graph_id from parameter."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=1
        )
        mock_type_def_repo = Mock()
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name"},
        )

        jsonl_content = '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":["slug","name"]}\n{"op":"CREATE","type":"node","id":"person:abc123def456789a","label":"person","set_properties":{"slug":"alice","name":"Alice","data_source_id":"ds-123","source_path":"people/alice.md"}}'

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        service.apply_mutations_from_jsonl(jsonl_content, knowledge_graph_id="kg-789")

        # Applier should receive CREATE op with knowledge_graph_id stamped
        applied_ops = mock_applier.apply_batch.call_args[0][0]
        create_op = next(o for o in applied_ops if o.op == MutationOperationType.CREATE)
        assert create_op.set_properties.get("knowledge_graph_id") == "kg-789"


class TestMutationResultErrorKind:
    """Tests that error_kind is set correctly on MutationResult failures.

    The error_kind field allows the presentation layer to select the correct
    HTTP status code (422 for validation, 500 for server errors) without
    parsing error message text.
    """

    def test_missing_type_definition_yields_validation_error_kind(self):
        """CREATE with no DEFINE should yield error_kind='validation'."""
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

        assert result.success is False
        assert result.error_kind == "validation"

    def test_missing_required_properties_yields_validation_error_kind(self):
        """CREATE with missing required props should yield error_kind='validation'."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_type_def_repo = Mock()
        mock_type_def_repo.get.return_value = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name", "email"},
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
                    # email is required but missing
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

        assert result.success is False
        assert result.error_kind == "validation"

    def test_json_parse_error_yields_validation_error_kind(self):
        """JSON parse failure in JSONL should yield error_kind='validation'."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_type_def_repo = Mock()

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations_from_jsonl("{not valid json")

        assert result.success is False
        assert result.error_kind == "validation"

    def test_pydantic_validation_error_yields_validation_error_kind(self):
        """Pydantic schema violation in JSONL should yield error_kind='validation'."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_type_def_repo = Mock()

        # Missing required 'op' field — valid JSON, invalid MutationOperation
        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations_from_jsonl('{"type":"node","id":"node:abc"}')

        assert result.success is False
        assert result.error_kind == "validation"

    def test_successful_mutation_has_no_error_kind(self):
        """Successful MutationResult should have error_kind=None."""
        from graph.application.services import GraphMutationService

        mock_applier = Mock()
        mock_applier.apply_batch.return_value = MutationResult(
            success=True, operations_applied=0
        )
        mock_type_def_repo = Mock()

        service = GraphMutationService(
            mutation_applier=mock_applier,
            type_definition_repository=mock_type_def_repo,
        )
        result = service.apply_mutations([])

        assert result.success is True
        assert result.error_kind is None
