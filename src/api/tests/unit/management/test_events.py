"""Unit tests for Management domain events."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

import pytest

from management.domain.events import (
    DataSourceCreated,
    DataSourceDeleted,
    DataSourceSyncRequested,
    DataSourceUpdated,
    DomainEvent,
    KnowledgeGraphCreated,
    KnowledgeGraphDeleted,
    KnowledgeGraphUpdated,
)


class TestKnowledgeGraphCreated:
    """Tests for KnowledgeGraphCreated event."""

    def test_stores_all_fields(self):
        now = datetime.now(UTC)
        event = KnowledgeGraphCreated(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
            name="My Graph",
            description="A test graph",
            occurred_at=now,
            created_by="user-abc",
        )
        assert event.knowledge_graph_id == "kg-123"
        assert event.tenant_id == "tenant-456"
        assert event.workspace_id == "ws-789"
        assert event.name == "My Graph"
        assert event.description == "A test graph"
        assert event.occurred_at == now
        assert event.created_by == "user-abc"

    def test_created_by_defaults_to_none(self):
        now = datetime.now(UTC)
        event = KnowledgeGraphCreated(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
            name="My Graph",
            description="A test graph",
            occurred_at=now,
        )
        assert event.created_by is None

    def test_is_frozen(self):
        now = datetime.now(UTC)
        event = KnowledgeGraphCreated(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
            name="My Graph",
            description="A test graph",
            occurred_at=now,
        )
        with pytest.raises(AttributeError):
            event.name = "changed"


class TestKnowledgeGraphUpdated:
    """Tests for KnowledgeGraphUpdated event."""

    def test_stores_all_fields(self):
        now = datetime.now(UTC)
        event = KnowledgeGraphUpdated(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            name="Updated Graph",
            description="Updated description",
            occurred_at=now,
            updated_by="user-abc",
        )
        assert event.knowledge_graph_id == "kg-123"
        assert event.tenant_id == "tenant-456"
        assert event.name == "Updated Graph"
        assert event.description == "Updated description"
        assert event.occurred_at == now
        assert event.updated_by == "user-abc"

    def test_updated_by_defaults_to_none(self):
        now = datetime.now(UTC)
        event = KnowledgeGraphUpdated(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            name="Updated Graph",
            description="Updated description",
            occurred_at=now,
        )
        assert event.updated_by is None


class TestKnowledgeGraphDeleted:
    """Tests for KnowledgeGraphDeleted event."""

    def test_stores_all_fields(self):
        now = datetime.now(UTC)
        event = KnowledgeGraphDeleted(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
            occurred_at=now,
            deleted_by="user-abc",
        )
        assert event.knowledge_graph_id == "kg-123"
        assert event.tenant_id == "tenant-456"
        assert event.workspace_id == "ws-789"
        assert event.occurred_at == now
        assert event.deleted_by == "user-abc"

    def test_includes_workspace_id(self):
        """KnowledgeGraphDeleted MUST include workspace_id per acceptance criteria."""
        now = datetime.now(UTC)
        event = KnowledgeGraphDeleted(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
            occurred_at=now,
        )
        assert hasattr(event, "workspace_id")
        assert event.workspace_id == "ws-789"

    def test_deleted_by_defaults_to_none(self):
        now = datetime.now(UTC)
        event = KnowledgeGraphDeleted(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
            occurred_at=now,
        )
        assert event.deleted_by is None


class TestDataSourceCreated:
    """Tests for DataSourceCreated event."""

    def test_stores_all_fields(self):
        now = datetime.now(UTC)
        event = DataSourceCreated(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            name="GitHub Repo",
            adapter_type="github",
            occurred_at=now,
            created_by="user-abc",
        )
        assert event.data_source_id == "ds-123"
        assert event.knowledge_graph_id == "kg-456"
        assert event.tenant_id == "tenant-789"
        assert event.name == "GitHub Repo"
        assert event.adapter_type == "github"
        assert event.occurred_at == now
        assert event.created_by == "user-abc"

    def test_created_by_defaults_to_none(self):
        now = datetime.now(UTC)
        event = DataSourceCreated(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            name="GitHub Repo",
            adapter_type="github",
            occurred_at=now,
        )
        assert event.created_by is None


class TestDataSourceUpdated:
    """Tests for DataSourceUpdated event."""

    def test_stores_all_fields(self):
        now = datetime.now(UTC)
        event = DataSourceUpdated(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            name="Updated Source",
            occurred_at=now,
            updated_by="user-abc",
        )
        assert event.data_source_id == "ds-123"
        assert event.knowledge_graph_id == "kg-456"
        assert event.tenant_id == "tenant-789"
        assert event.name == "Updated Source"
        assert event.occurred_at == now
        assert event.updated_by == "user-abc"

    def test_updated_by_defaults_to_none(self):
        now = datetime.now(UTC)
        event = DataSourceUpdated(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            name="Updated Source",
            occurred_at=now,
        )
        assert event.updated_by is None


class TestDataSourceDeleted:
    """Tests for DataSourceDeleted event."""

    def test_stores_all_fields(self):
        now = datetime.now(UTC)
        event = DataSourceDeleted(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            occurred_at=now,
            deleted_by="user-abc",
        )
        assert event.data_source_id == "ds-123"
        assert event.knowledge_graph_id == "kg-456"
        assert event.tenant_id == "tenant-789"
        assert event.occurred_at == now
        assert event.deleted_by == "user-abc"

    def test_deleted_by_defaults_to_none(self):
        now = datetime.now(UTC)
        event = DataSourceDeleted(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            occurred_at=now,
        )
        assert event.deleted_by is None


class TestDataSourceSyncRequested:
    """Tests for DataSourceSyncRequested event."""

    def test_stores_all_fields(self):
        now = datetime.now(UTC)
        event = DataSourceSyncRequested(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            occurred_at=now,
            requested_by="user-abc",
        )
        assert event.data_source_id == "ds-123"
        assert event.knowledge_graph_id == "kg-456"
        assert event.tenant_id == "tenant-789"
        assert event.occurred_at == now
        assert event.requested_by == "user-abc"

    def test_requested_by_defaults_to_none(self):
        now = datetime.now(UTC)
        event = DataSourceSyncRequested(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            occurred_at=now,
        )
        assert event.requested_by is None


_ALL_EVENT_TYPES = [
    KnowledgeGraphCreated,
    KnowledgeGraphUpdated,
    KnowledgeGraphDeleted,
    DataSourceCreated,
    DataSourceUpdated,
    DataSourceDeleted,
    DataSourceSyncRequested,
]

_ALLOWED_FIELD_TYPES = {"str", "datetime", "str | None"}


class TestDomainEventUnion:
    """Tests for the DomainEvent type alias."""

    def test_all_event_types_in_union(self):
        """DomainEvent union should include all Management event types."""
        union_types = (
            set(DomainEvent.__args__) if hasattr(DomainEvent, "__args__") else set()
        )
        expected = set(_ALL_EVENT_TYPES)
        assert expected == union_types, (
            f"Missing from DomainEvent union: {expected - union_types}"
        )

    @pytest.mark.parametrize("event_type", _ALL_EVENT_TYPES, ids=lambda t: t.__name__)
    def test_event_is_frozen(self, event_type):
        """All domain events must be immutable frozen dataclasses."""
        assert event_type.__dataclass_params__.frozen, (
            f"{event_type.__name__} is not frozen"
        )

    @pytest.mark.parametrize("event_type", _ALL_EVENT_TYPES, ids=lambda t: t.__name__)
    def test_event_uses_only_primitive_types(self, event_type):
        """All event fields must use only primitive types (str, datetime, str | None)."""
        for f in fields(event_type):
            assert f.type in _ALLOWED_FIELD_TYPES, (
                f"{event_type.__name__}.{f.name} has non-primitive type: {f.type}"
            )
