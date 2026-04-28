"""Unit tests for knowledge_graph_id stamping in GraphMutationService.

Spec: specs/graph/mutations.spec.md
Requirement: KnowledgeGraph Scoping

Tests verify that:
- The service stamps knowledge_graph_id on all CREATE/UPDATE operations
- Caller-provided knowledge_graph_id is stripped (anti-spoofing)
- knowledge_graph_id is excluded from schema learning (optional properties)
"""

from __future__ import annotations

from graph.application.services.graph_mutation_service import GraphMutationService
from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
    MutationResult,
    TypeDefinition,
)


class FakeMutationApplier:
    """In-memory fake for IMutationApplier that captures submitted operations."""

    def __init__(self) -> None:
        self.received_operations: list[MutationOperation] = []
        self.should_succeed = True

    def apply_batch(self, operations: list[MutationOperation]) -> MutationResult:
        self.received_operations = list(operations)
        if self.should_succeed:
            return MutationResult(success=True, operations_applied=len(operations))
        return MutationResult(success=False, operations_applied=0, errors=["Failure"])


class FakeTypeDefinitionRepository:
    """In-memory fake for ITypeDefinitionRepository."""

    def __init__(self, type_defs: dict[tuple[str, str], TypeDefinition] | None = None):
        self._defs: dict[tuple[str, str], TypeDefinition] = type_defs or {}
        self.saves: list[TypeDefinition] = []

    def save(self, type_def: TypeDefinition) -> None:
        self._defs[(type_def.label, type_def.entity_type)] = type_def
        self.saves.append(type_def)

    def get(self, label: str, entity_type: str) -> TypeDefinition | None:
        return self._defs.get((label, entity_type))

    def get_all(self) -> list[TypeDefinition]:
        return list(self._defs.values())

    def delete(self, label: str, entity_type: str) -> bool:
        key = (label, entity_type)
        if key in self._defs:
            del self._defs[key]
            return True
        return False


def make_type_def(label: str, entity_type: EntityType) -> TypeDefinition:
    """Helper to create a type definition."""
    return TypeDefinition(
        label=label,
        entity_type=entity_type,
        description=f"A {label}",
        required_properties={"slug", "name"}
        if entity_type == EntityType.NODE
        else {"since"},
    )


class TestKnowledgeGraphIdStamping:
    """Tests for knowledge_graph_id stamping on CREATE and UPDATE operations."""

    def test_stamps_knowledge_graph_id_on_create_node(self):
        """Service must stamp knowledge_graph_id on CREATE node operations."""
        applier = FakeMutationApplier()
        type_repo = FakeTypeDefinitionRepository(
            type_defs={
                ("person", EntityType.NODE): make_type_def("person", EntityType.NODE)
            }
        )
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        create_op = MutationOperation(
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
        )

        result = service.apply_mutations(
            operations=[create_op],
            knowledge_graph_id="kg-123",
        )

        assert result.success is True
        # Verify the operation passed to applier has knowledge_graph_id stamped
        applied_ops = applier.received_operations
        assert len(applied_ops) == 1
        assert applied_ops[0].set_properties is not None
        assert applied_ops[0].set_properties["knowledge_graph_id"] == "kg-123"

    def test_stamps_knowledge_graph_id_on_create_edge(self):
        """Service must stamp knowledge_graph_id on CREATE edge operations."""
        applier = FakeMutationApplier()
        type_repo = FakeTypeDefinitionRepository(
            type_defs={
                ("knows", EntityType.EDGE): TypeDefinition(
                    label="knows",
                    entity_type=EntityType.EDGE,
                    description="Knows edge",
                    required_properties={"since"},
                )
            }
        )
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
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
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )

        result = service.apply_mutations(
            operations=[create_op],
            knowledge_graph_id="kg-456",
        )

        assert result.success is True
        applied_ops = applier.received_operations
        assert applied_ops[0].set_properties is not None
        assert applied_ops[0].set_properties["knowledge_graph_id"] == "kg-456"

    def test_stamps_knowledge_graph_id_on_update(self):
        """Service must stamp knowledge_graph_id on UPDATE operations."""
        applier = FakeMutationApplier()
        type_repo = FakeTypeDefinitionRepository()
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        update_op = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            set_properties={"name": "Alice Updated"},
        )

        service.apply_mutations(
            operations=[update_op],
            knowledge_graph_id="kg-789",
        )

        applied_ops = applier.received_operations
        assert len(applied_ops) == 1
        assert applied_ops[0].set_properties is not None
        assert applied_ops[0].set_properties["knowledge_graph_id"] == "kg-789"

    def test_strips_caller_provided_knowledge_graph_id_on_create(self):
        """Service must strip and override caller-provided knowledge_graph_id (anti-spoofing)."""
        applier = FakeMutationApplier()
        type_repo = FakeTypeDefinitionRepository(
            type_defs={
                ("person", EntityType.NODE): make_type_def("person", EntityType.NODE)
            }
        )
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        # Caller tries to spoof a different knowledge_graph_id
        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice",
                "name": "Alice",
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
                "knowledge_graph_id": "kg-spoofed",  # Caller tries to spoof!
            },
        )

        service.apply_mutations(
            operations=[create_op],
            knowledge_graph_id="kg-authorized",  # Authorized value from server
        )

        applied_ops = applier.received_operations
        assert applied_ops[0].set_properties is not None
        # Caller's value should be replaced with the authorized value
        assert applied_ops[0].set_properties["knowledge_graph_id"] == "kg-authorized"
        assert applied_ops[0].set_properties["knowledge_graph_id"] != "kg-spoofed"

    def test_strips_caller_provided_knowledge_graph_id_on_update(self):
        """Service must strip and override caller-provided knowledge_graph_id in UPDATE."""
        applier = FakeMutationApplier()
        type_repo = FakeTypeDefinitionRepository()
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        update_op = MutationOperation(
            op=MutationOperationType.UPDATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            set_properties={
                "name": "Alice",
                "knowledge_graph_id": "kg-spoofed",  # Spoofed!
            },
        )

        service.apply_mutations(
            operations=[update_op],
            knowledge_graph_id="kg-authorized",
        )

        applied_ops = applier.received_operations
        assert applied_ops[0].set_properties["knowledge_graph_id"] == "kg-authorized"

    def test_does_not_stamp_on_define(self):
        """Service must NOT add knowledge_graph_id to DEFINE operations."""
        applier = FakeMutationApplier()
        type_repo = FakeTypeDefinitionRepository()
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        define_op = MutationOperation(
            op=MutationOperationType.DEFINE,
            type=EntityType.NODE,
            label="person",
            description="A person",
            required_properties={"slug", "name"},
        )

        service.apply_mutations(
            operations=[define_op],
            knowledge_graph_id="kg-123",
        )

        applied_ops = applier.received_operations
        assert len(applied_ops) == 1
        # DEFINE has no set_properties
        assert applied_ops[0].set_properties is None

    def test_does_not_stamp_on_delete(self):
        """Service must NOT add knowledge_graph_id to DELETE operations."""
        applier = FakeMutationApplier()
        type_repo = FakeTypeDefinitionRepository()
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        delete_op = MutationOperation(
            op=MutationOperationType.DELETE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
        )

        service.apply_mutations(
            operations=[delete_op],
            knowledge_graph_id="kg-123",
        )

        applied_ops = applier.received_operations
        assert len(applied_ops) == 1
        assert applied_ops[0].set_properties is None

    def test_works_without_knowledge_graph_id(self):
        """Service should work without knowledge_graph_id for backward compatibility."""
        applier = FakeMutationApplier()
        type_repo = FakeTypeDefinitionRepository()
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        delete_op = MutationOperation(
            op=MutationOperationType.DELETE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
        )

        # Called without knowledge_graph_id (no stamping)
        result = service.apply_mutations(operations=[delete_op])
        assert result.success is True


class TestKnowledgeGraphIdExcludedFromSchemaLearning:
    """Tests that knowledge_graph_id is excluded from schema learning (optional properties)."""

    def test_knowledge_graph_id_not_added_to_optional_properties(self):
        """Schema learning should NOT add knowledge_graph_id to optional_properties."""
        applier = FakeMutationApplier()
        existing_type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name"},
            optional_properties=set(),
        )
        type_repo = FakeTypeDefinitionRepository(
            type_defs={("person", EntityType.NODE): existing_type_def}
        )
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        # CREATE with knowledge_graph_id (server-stamped)
        create_op = MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="person:abc123def456789a",
            label="person",
            set_properties={
                "slug": "alice",
                "name": "Alice",
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
                "knowledge_graph_id": "kg-123",
            },
        )

        service.apply_mutations(
            operations=[create_op],
            knowledge_graph_id="kg-123",
        )

        # knowledge_graph_id should NOT be in optional_properties
        saved_defs = type_repo.saves
        if saved_defs:
            # If a type def was saved (schema learning occurred), ensure kg_id not in optional
            final_def = saved_defs[-1]
            assert "knowledge_graph_id" not in final_def.optional_properties
        # Also verify the type_repo doesn't have kg_id in optional
        final_type = type_repo.get("person", EntityType.NODE)
        assert final_type is not None
        assert "knowledge_graph_id" not in (final_type.optional_properties or set())


class TestKnowledgeGraphIdJsonlStamping:
    """Tests for knowledge_graph_id stamping via apply_mutations_from_jsonl."""

    def test_jsonl_stamping_applies_knowledge_graph_id(self):
        """apply_mutations_from_jsonl should propagate knowledge_graph_id for stamping."""
        applier = FakeMutationApplier()
        existing_type_def = TypeDefinition(
            label="person",
            entity_type=EntityType.NODE,
            description="A person",
            required_properties={"slug", "name"},
        )
        type_repo = FakeTypeDefinitionRepository(
            type_defs={("person", EntityType.NODE): existing_type_def}
        )
        service = GraphMutationService(
            mutation_applier=applier,
            type_definition_repository=type_repo,
        )

        jsonl_content = '{"op":"CREATE","type":"node","id":"person:abc123def456789a","label":"person","set_properties":{"slug":"alice","name":"Alice","data_source_id":"ds-123","source_path":"people/alice.md"}}'

        result = service.apply_mutations_from_jsonl(
            jsonl_content=jsonl_content,
            knowledge_graph_id="kg-from-route",
        )

        assert result.success is True
        applied_ops = applier.received_operations
        assert len(applied_ops) == 1
        assert applied_ops[0].set_properties is not None
        assert applied_ops[0].set_properties["knowledge_graph_id"] == "kg-from-route"
