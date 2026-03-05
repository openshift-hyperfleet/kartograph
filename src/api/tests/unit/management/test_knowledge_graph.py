"""Unit tests for KnowledgeGraph aggregate."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from management.domain.aggregates.knowledge_graph import KnowledgeGraph
from management.domain.events import (
    KnowledgeGraphCreated,
    KnowledgeGraphDeleted,
    KnowledgeGraphUpdated,
)
from management.domain.exceptions import InvalidKnowledgeGraphNameError
from management.domain.observability import (
    KnowledgeGraphProbe,
)
from management.domain.value_objects import KnowledgeGraphId


class TestKnowledgeGraphCreate:
    """Tests for KnowledgeGraph.create() factory method."""

    def test_create_sets_all_fields(self):
        """create() should set all fields correctly."""
        kg = KnowledgeGraph.create(
            tenant_id="tenant-123",
            workspace_id="ws-456",
            name="My Graph",
            description="A test knowledge graph",
        )
        assert isinstance(kg.id, KnowledgeGraphId)
        assert kg.tenant_id == "tenant-123"
        assert kg.workspace_id == "ws-456"
        assert kg.name == "My Graph"
        assert kg.description == "A test knowledge graph"
        assert isinstance(kg.created_at, datetime)
        assert isinstance(kg.updated_at, datetime)
        assert kg.created_at == kg.updated_at

    def test_create_generates_unique_id(self):
        """Each create() call should generate a unique ID."""
        kg1 = KnowledgeGraph.create(
            tenant_id="t", workspace_id="w", name="Graph 1", description=""
        )
        kg2 = KnowledgeGraph.create(
            tenant_id="t", workspace_id="w", name="Graph 2", description=""
        )
        assert kg1.id != kg2.id

    def test_create_emits_knowledge_graph_created_event(self):
        """create() should emit a KnowledgeGraphCreated event."""
        kg = KnowledgeGraph.create(
            tenant_id="tenant-123",
            workspace_id="ws-456",
            name="My Graph",
            description="A test graph",
            created_by="user-abc",
        )
        events = kg.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, KnowledgeGraphCreated)
        assert event.knowledge_graph_id == kg.id.value
        assert event.tenant_id == "tenant-123"
        assert event.workspace_id == "ws-456"
        assert event.name == "My Graph"
        assert event.description == "A test graph"
        assert event.created_by == "user-abc"
        assert isinstance(event.occurred_at, datetime)

    def test_create_without_actor(self):
        """create() without created_by should set it to None in event."""
        kg = KnowledgeGraph.create(
            tenant_id="t", workspace_id="w", name="Graph", description=""
        )
        events = kg.collect_events()
        assert events[0].created_by is None

    def test_create_calls_probe(self):
        """create() should call the probe's created method."""
        probe = MagicMock(spec=KnowledgeGraphProbe)
        kg = KnowledgeGraph.create(
            tenant_id="tenant-123",
            workspace_id="ws-456",
            name="My Graph",
            description="desc",
            probe=probe,
        )
        probe.created.assert_called_once_with(
            knowledge_graph_id=kg.id.value,
            tenant_id="tenant-123",
            workspace_id="ws-456",
            name="My Graph",
        )

    def test_create_rejects_empty_name(self):
        """create() should raise error for empty name."""
        with pytest.raises(InvalidKnowledgeGraphNameError):
            KnowledgeGraph.create(
                tenant_id="t", workspace_id="w", name="", description=""
            )

    def test_create_rejects_name_over_100_chars(self):
        """create() should raise error for name exceeding 100 characters."""
        with pytest.raises(InvalidKnowledgeGraphNameError):
            KnowledgeGraph.create(
                tenant_id="t",
                workspace_id="w",
                name="x" * 101,
                description="",
            )

    def test_create_accepts_name_exactly_100_chars(self):
        """create() should accept name that is exactly 100 characters."""
        kg = KnowledgeGraph.create(
            tenant_id="t", workspace_id="w", name="x" * 100, description=""
        )
        assert len(kg.name) == 100

    def test_create_accepts_single_char_name(self):
        """create() should accept single character name."""
        kg = KnowledgeGraph.create(
            tenant_id="t", workspace_id="w", name="A", description=""
        )
        assert kg.name == "A"


class TestKnowledgeGraphUpdate:
    """Tests for KnowledgeGraph.update() method."""

    def _create_kg(self, **kwargs):
        """Helper to create a KG and clear creation events."""
        defaults = {
            "tenant_id": "t",
            "workspace_id": "w",
            "name": "Original",
            "description": "Original desc",
        }
        defaults.update(kwargs)
        kg = KnowledgeGraph.create(**defaults)
        kg.collect_events()  # clear creation event
        return kg

    def test_update_changes_name_and_description(self):
        """update() should change name and description."""
        kg = self._create_kg()
        kg.update(name="Updated", description="Updated desc")
        assert kg.name == "Updated"
        assert kg.description == "Updated desc"

    def test_update_advances_updated_at(self):
        """update() should advance updated_at timestamp."""
        kg = self._create_kg()
        original_updated_at = kg.updated_at
        kg.update(name="Updated", description="Updated desc")
        assert kg.updated_at >= original_updated_at

    def test_update_emits_knowledge_graph_updated_event(self):
        """update() should emit a KnowledgeGraphUpdated event."""
        kg = self._create_kg()
        kg.update(
            name="Updated",
            description="Updated desc",
            updated_by="user-xyz",
        )
        events = kg.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, KnowledgeGraphUpdated)
        assert event.knowledge_graph_id == kg.id.value
        assert event.tenant_id == kg.tenant_id
        assert event.name == "Updated"
        assert event.description == "Updated desc"
        assert event.updated_by == "user-xyz"

    def test_update_without_actor(self):
        """update() without updated_by should set it to None in event."""
        kg = self._create_kg()
        kg.update(name="Updated", description="Updated desc")
        events = kg.collect_events()
        assert events[0].updated_by is None

    def test_update_rejects_empty_name(self):
        """update() should raise error for empty name."""
        kg = self._create_kg()
        with pytest.raises(InvalidKnowledgeGraphNameError):
            kg.update(name="", description="desc")

    def test_update_rejects_name_over_100_chars(self):
        """update() should raise error for name exceeding 100 characters."""
        kg = self._create_kg()
        with pytest.raises(InvalidKnowledgeGraphNameError):
            kg.update(name="x" * 101, description="desc")

    def test_update_calls_probe(self):
        """update() should call the probe's updated method."""
        probe = MagicMock(spec=KnowledgeGraphProbe)
        kg = self._create_kg(probe=probe)
        probe.reset_mock()
        kg.update(name="Updated", description="Updated desc")
        probe.updated.assert_called_once_with(
            knowledge_graph_id=kg.id.value,
            tenant_id=kg.tenant_id,
            name="Updated",
        )


class TestKnowledgeGraphMarkForDeletion:
    """Tests for KnowledgeGraph.mark_for_deletion() method."""

    def _create_kg(self, **kwargs):
        """Helper to create a KG and clear creation events."""
        defaults = {
            "tenant_id": "tenant-123",
            "workspace_id": "ws-456",
            "name": "Graph",
            "description": "desc",
        }
        defaults.update(kwargs)
        kg = KnowledgeGraph.create(**defaults)
        kg.collect_events()
        return kg

    def test_mark_for_deletion_emits_deleted_event(self):
        """mark_for_deletion() should emit KnowledgeGraphDeleted event."""
        kg = self._create_kg()
        kg.mark_for_deletion()
        events = kg.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, KnowledgeGraphDeleted)
        assert event.knowledge_graph_id == kg.id.value
        assert event.tenant_id == "tenant-123"

    def test_mark_for_deletion_includes_workspace_id(self):
        """mark_for_deletion() MUST include workspace_id in deleted event (acceptance criteria)."""
        kg = self._create_kg()
        kg.mark_for_deletion()
        events = kg.collect_events()
        event = events[0]
        assert event.workspace_id == "ws-456"

    def test_mark_for_deletion_with_actor(self):
        """mark_for_deletion() should include deleted_by when provided."""
        kg = self._create_kg()
        kg.mark_for_deletion(deleted_by="user-abc")
        events = kg.collect_events()
        assert events[0].deleted_by == "user-abc"

    def test_mark_for_deletion_without_actor(self):
        """mark_for_deletion() without actor should set deleted_by to None."""
        kg = self._create_kg()
        kg.mark_for_deletion()
        events = kg.collect_events()
        assert events[0].deleted_by is None

    def test_mark_for_deletion_calls_probe(self):
        """mark_for_deletion() should call the probe's deleted method."""
        probe = MagicMock(spec=KnowledgeGraphProbe)
        kg = self._create_kg(probe=probe)
        probe.reset_mock()
        kg.mark_for_deletion()
        probe.deleted.assert_called_once_with(
            knowledge_graph_id=kg.id.value,
            tenant_id="tenant-123",
            workspace_id="ws-456",
        )


class TestKnowledgeGraphCollectEvents:
    """Tests for KnowledgeGraph.collect_events() method."""

    def test_collect_events_returns_pending_events(self):
        """collect_events() should return all pending events."""
        kg = KnowledgeGraph.create(
            tenant_id="t", workspace_id="w", name="Graph", description=""
        )
        events = kg.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], KnowledgeGraphCreated)

    def test_collect_events_clears_pending_events(self):
        """collect_events() should clear the pending events list."""
        kg = KnowledgeGraph.create(
            tenant_id="t", workspace_id="w", name="Graph", description=""
        )
        kg.collect_events()
        events = kg.collect_events()
        assert events == []

    def test_collect_events_returns_multiple_events_in_order(self):
        """collect_events() should return events in the order they were recorded."""
        kg = KnowledgeGraph.create(
            tenant_id="t", workspace_id="w", name="Graph", description=""
        )
        kg.update(name="Updated", description="Updated desc")
        kg.mark_for_deletion()
        events = kg.collect_events()
        assert len(events) == 3
        assert isinstance(events[0], KnowledgeGraphCreated)
        assert isinstance(events[1], KnowledgeGraphUpdated)
        assert isinstance(events[2], KnowledgeGraphDeleted)


class TestKnowledgeGraphValidation:
    """Tests for KnowledgeGraph.__post_init__ validation."""

    def test_post_init_rejects_empty_name(self):
        """Direct construction with empty name should raise."""
        with pytest.raises(InvalidKnowledgeGraphNameError):
            KnowledgeGraph(
                id=KnowledgeGraphId.generate(),
                tenant_id="t",
                workspace_id="w",
                name="",
                description="",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_post_init_rejects_name_over_100_chars(self):
        """Direct construction with name > 100 chars should raise."""
        with pytest.raises(InvalidKnowledgeGraphNameError):
            KnowledgeGraph(
                id=KnowledgeGraphId.generate(),
                tenant_id="t",
                workspace_id="w",
                name="x" * 101,
                description="",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
