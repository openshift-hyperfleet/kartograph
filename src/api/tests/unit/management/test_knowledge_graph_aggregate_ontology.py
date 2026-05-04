"""Unit tests for KnowledgeGraph aggregate ontology methods."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from management.domain.aggregates.knowledge_graph import KnowledgeGraph
from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
)


def make_kg(
    tenant_id: str = "tenant-123",
    workspace_id: str = "ws-456",
    name: str = "Test Graph",
    description: str = "Test description",
) -> KnowledgeGraph:
    """Helper: create a KG with sensible defaults and clear creation events."""
    kg = KnowledgeGraph.create(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        name=name,
        description=description,
    )
    kg.collect_events()  # clear the KnowledgeGraphCreated event
    return kg


def make_ontology_config() -> OntologyConfig:
    """Helper: create a minimal OntologyConfig."""
    nt = NodeTypeDefinition(
        label="Repository",
        description="A GitHub repository",
        required_properties=("url",),
    )
    et = EdgeTypeDefinition(
        label="CONTAINS",
        description="",
        source_labels=("Repository",),
        target_labels=("File",),
    )
    return OntologyConfig(node_types=(nt,), edge_types=(et,))


class TestKnowledgeGraphOntologyDefault:
    """Tests for the default ontology state on KnowledgeGraph."""

    def test_ontology_is_none_by_default(self):
        """A newly created KnowledgeGraph should have ontology=None."""
        kg = make_kg()
        assert kg.ontology is None

    def test_ontology_none_after_create_factory(self):
        """KnowledgeGraph.create() should produce ontology=None."""
        kg = KnowledgeGraph.create(
            tenant_id="t",
            workspace_id="w",
            name="Graph",
            description="",
        )
        assert kg.ontology is None


class TestKnowledgeGraphSetOntology:
    """Tests for KnowledgeGraph.set_ontology() method."""

    def test_set_ontology_stores_config(self):
        """set_ontology() should store the provided OntologyConfig."""
        kg = make_kg()
        config = make_ontology_config()
        kg.set_ontology(config)
        assert kg.ontology is config

    def test_set_ontology_updates_updated_at(self):
        """set_ontology() should advance updated_at."""
        kg = make_kg()
        original_updated_at = kg.updated_at
        config = make_ontology_config()
        kg.set_ontology(config)
        assert kg.updated_at >= original_updated_at

    def test_set_ontology_replaces_previous_ontology(self):
        """set_ontology() should replace any previous OntologyConfig."""
        kg = make_kg()
        config1 = OntologyConfig(
            node_types=(NodeTypeDefinition(label="A", description=""),)
        )
        config2 = OntologyConfig(
            node_types=(NodeTypeDefinition(label="B", description=""),)
        )
        kg.set_ontology(config1)
        kg.set_ontology(config2)
        assert kg.ontology == config2
        assert kg.ontology.node_types[0].label == "B"

    def test_set_ontology_raises_on_deleted_kg(self):
        """set_ontology() should raise AggregateDeletedError if KG was deleted."""
        from management.domain.exceptions import AggregateDeletedError

        kg = make_kg()
        kg.mark_for_deletion()
        config = make_ontology_config()
        with pytest.raises(AggregateDeletedError):
            kg.set_ontology(config)

    def test_set_ontology_with_empty_config(self):
        """set_ontology() with empty OntologyConfig should succeed."""
        kg = make_kg()
        empty = OntologyConfig()
        kg.set_ontology(empty)
        assert kg.ontology is not None
        assert kg.ontology.node_types == ()
        assert kg.ontology.edge_types == ()

    def test_set_ontology_with_approved_at(self):
        """set_ontology() should accept an approved OntologyConfig."""
        kg = make_kg()
        now = datetime.now(UTC)
        config = OntologyConfig(approved_at=now)
        kg.set_ontology(config)
        assert kg.ontology is not None
        assert kg.ontology.approved_at == now

    def test_set_ontology_does_not_emit_domain_events(self):
        """set_ontology() should NOT emit domain events (no outbox publishing)."""
        kg = make_kg()
        config = make_ontology_config()
        kg.set_ontology(config)
        events = kg.collect_events()
        assert events == []


class TestKnowledgeGraphClearOntology:
    """Tests for KnowledgeGraph.clear_ontology() method."""

    def test_clear_ontology_resets_to_none(self):
        """clear_ontology() should set ontology back to None."""
        kg = make_kg()
        config = make_ontology_config()
        kg.set_ontology(config)
        kg.clear_ontology()
        assert kg.ontology is None

    def test_clear_ontology_updates_updated_at(self):
        """clear_ontology() should advance updated_at."""
        kg = make_kg()
        config = make_ontology_config()
        kg.set_ontology(config)
        original_updated_at = kg.updated_at
        kg.clear_ontology()
        assert kg.updated_at >= original_updated_at

    def test_clear_ontology_when_already_none_is_noop(self):
        """clear_ontology() when ontology is already None should not error."""
        kg = make_kg()
        assert kg.ontology is None
        kg.clear_ontology()  # should not raise
        assert kg.ontology is None

    def test_clear_ontology_does_not_emit_domain_events(self):
        """clear_ontology() should NOT emit domain events."""
        kg = make_kg()
        config = make_ontology_config()
        kg.set_ontology(config)
        kg.collect_events()  # clear any events
        kg.clear_ontology()
        events = kg.collect_events()
        assert events == []

    def test_clear_ontology_raises_on_deleted_kg(self):
        """clear_ontology() should raise AggregateDeletedError if KG was deleted."""
        from management.domain.exceptions import AggregateDeletedError

        kg = make_kg()
        config = make_ontology_config()
        kg.set_ontology(config)
        kg.mark_for_deletion()
        with pytest.raises(AggregateDeletedError):
            kg.clear_ontology()


class TestInMemoryKnowledgeGraphRepositoryOntology:
    """Tests for InMemoryKnowledgeGraphRepository ontology methods."""

    def _make_repo(self):
        from tests.fakes.management import InMemoryKnowledgeGraphRepository

        return InMemoryKnowledgeGraphRepository()

    @pytest.mark.asyncio
    async def test_save_ontology_and_get_ontology_round_trip(self):
        """save_ontology / get_ontology should round-trip correctly."""
        repo = self._make_repo()
        kg = make_kg()
        await repo.save(kg)
        config = make_ontology_config()
        await repo.save_ontology(kg.id.value, config)
        result = await repo.get_ontology(kg.id.value)
        assert result == config

    @pytest.mark.asyncio
    async def test_get_ontology_returns_none_when_not_set(self):
        """get_ontology() should return None when no ontology saved."""
        repo = self._make_repo()
        kg = make_kg()
        await repo.save(kg)
        result = await repo.get_ontology(kg.id.value)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_ontology_returns_none_for_unknown_kg(self):
        """get_ontology() should return None for an unknown KG ID."""
        repo = self._make_repo()
        result = await repo.get_ontology("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_ontology_replaces_previous(self):
        """Calling save_ontology() twice should replace the first ontology."""
        repo = self._make_repo()
        kg = make_kg()
        await repo.save(kg)
        config1 = OntologyConfig(
            node_types=(NodeTypeDefinition(label="A", description=""),)
        )
        config2 = OntologyConfig(
            node_types=(NodeTypeDefinition(label="B", description=""),)
        )
        await repo.save_ontology(kg.id.value, config1)
        await repo.save_ontology(kg.id.value, config2)
        result = await repo.get_ontology(kg.id.value)
        assert result is not None
        assert result.node_types[0].label == "B"

    @pytest.mark.asyncio
    async def test_save_ontology_stores_empty_config(self):
        """save_ontology() with empty OntologyConfig should persist correctly."""
        repo = self._make_repo()
        kg = make_kg()
        await repo.save(kg)
        empty = OntologyConfig()
        await repo.save_ontology(kg.id.value, empty)
        result = await repo.get_ontology(kg.id.value)
        assert result is not None
        assert result.node_types == ()
        assert result.edge_types == ()
