"""Unit tests for ManagementEventSerializer.

These tests verify that Management domain events are correctly serialized
and deserialized for outbox storage, following the same pattern as
IAM's test_serializer.py.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from management.domain.events import (
    DataSourceCreated,
    DataSourceDeleted,
    DataSourceUpdated,
    DomainEvent,
    KnowledgeGraphCreated,
    KnowledgeGraphDeleted,
    KnowledgeGraphUpdated,
    SyncStarted,
)
from management.infrastructure.outbox import ManagementEventSerializer


class TestSupportedEvents:
    """Tests for supported event types."""

    def test_supports_all_management_domain_events(self):
        """Serializer should support all Management domain event types."""
        serializer = ManagementEventSerializer()
        supported = serializer.supported_event_types()

        assert "KnowledgeGraphCreated" in supported
        assert "KnowledgeGraphUpdated" in supported
        assert "KnowledgeGraphDeleted" in supported
        assert "DataSourceCreated" in supported
        assert "DataSourceUpdated" in supported
        assert "DataSourceDeleted" in supported
        assert "SyncStarted" in supported

    def test_supported_count_matches_domain_event_union(self):
        """Supported types count should match the DomainEvent type alias members."""
        serializer = ManagementEventSerializer()
        supported = serializer.supported_event_types()

        assert len(supported) == 7


class TestSerialize:
    """Tests for serialize method."""

    def test_serializes_knowledge_graph_created(self):
        """KnowledgeGraphCreated should be serialized correctly."""
        serializer = ManagementEventSerializer()
        occurred_at = datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)
        event = KnowledgeGraphCreated(
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNXX",
            name="Test Graph",
            description="A test knowledge graph",
            occurred_at=occurred_at,
            created_by="user-123",
        )

        payload = serializer.serialize(event)

        assert payload["knowledge_graph_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["tenant_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert payload["workspace_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNXX"
        assert payload["name"] == "Test Graph"
        assert payload["description"] == "A test knowledge graph"
        assert payload["occurred_at"] == "2026-03-10T12:00:00+00:00"
        assert payload["created_by"] == "user-123"

    def test_serializes_knowledge_graph_created_without_created_by(self):
        """KnowledgeGraphCreated should handle None created_by."""
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphCreated(
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNXX",
            name="Test Graph",
            description="",
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(event)

        assert payload["created_by"] is None

    def test_serializes_knowledge_graph_updated(self):
        """KnowledgeGraphUpdated should be serialized correctly."""
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphUpdated(
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            name="Updated Name",
            description="Updated description",
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(event)

        assert payload["knowledge_graph_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["name"] == "Updated Name"
        assert payload["description"] == "Updated description"

    def test_serializes_knowledge_graph_deleted(self):
        """KnowledgeGraphDeleted should include workspace_id."""
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphDeleted(
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNXX",
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(event)

        assert payload["knowledge_graph_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["workspace_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNXX"

    def test_serializes_data_source_created(self):
        """DataSourceCreated should be serialized correctly."""
        serializer = ManagementEventSerializer()
        event = DataSourceCreated(
            data_source_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            name="My GitHub Source",
            adapter_type="github",
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(event)

        assert payload["data_source_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert payload["knowledge_graph_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["adapter_type"] == "github"

    def test_serializes_data_source_updated(self):
        """DataSourceUpdated should be serialized correctly."""
        serializer = ManagementEventSerializer()
        event = DataSourceUpdated(
            data_source_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            name="Updated Source",
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(event)

        assert payload["data_source_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert payload["name"] == "Updated Source"

    def test_serializes_data_source_deleted(self):
        """DataSourceDeleted should be serialized correctly."""
        serializer = ManagementEventSerializer()
        event = DataSourceDeleted(
            data_source_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(event)

        assert payload["data_source_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert payload["knowledge_graph_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"

    def test_serializes_sync_started(self):
        """SyncStarted should be serialized correctly including connection_config."""
        serializer = ManagementEventSerializer()
        event = SyncStarted(
            sync_run_id="01ARZCX0P0HZGQP3MZXQQ0NNVV",
            data_source_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            adapter_type="github",
            connection_config={"repo": "org/repo"},
            credentials_path=None,
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
            requested_by="user-456",
        )

        payload = serializer.serialize(event)

        assert payload["sync_run_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNVV"
        assert payload["data_source_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert payload["adapter_type"] == "github"
        assert payload["connection_config"] == {"repo": "org/repo"}
        assert payload["requested_by"] == "user-456"

    def test_payload_is_json_serializable(self):
        """Serialized payload should be JSON-compatible."""
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphCreated(
            knowledge_graph_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNXX",
            name="Test Graph",
            description="Test",
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(event)
        json_str = json.dumps(payload)

        assert isinstance(json_str, str)

    def test_raises_for_unsupported_event(self):
        """Serializer should raise for unsupported event types."""
        serializer = ManagementEventSerializer()

        @dataclass(frozen=True)
        class UnknownEvent:
            data: str

        with pytest.raises(ValueError, match="Unsupported event type"):
            serializer.serialize(UnknownEvent(data="test"))


class TestDeserialize:
    """Tests for deserialize method."""

    def test_deserializes_knowledge_graph_created(self):
        """KnowledgeGraphCreated should be deserialized correctly."""
        serializer = ManagementEventSerializer()
        payload = {
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "workspace_id": "01ARZCX0P0HZGQP3MZXQQ0NNXX",
            "name": "Test Graph",
            "description": "A test knowledge graph",
            "occurred_at": "2026-03-10T12:00:00+00:00",
            "created_by": "user-123",
        }

        event = serializer.deserialize("KnowledgeGraphCreated", payload)

        assert isinstance(event, KnowledgeGraphCreated)
        assert event.knowledge_graph_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.occurred_at == datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)
        assert event.created_by == "user-123"

    def test_deserializes_data_source_created(self):
        """DataSourceCreated should be deserialized correctly."""
        serializer = ManagementEventSerializer()
        payload = {
            "data_source_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "knowledge_graph_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "name": "GitHub Source",
            "adapter_type": "github",
            "occurred_at": "2026-03-10T12:00:00+00:00",
            "created_by": None,
        }

        event = serializer.deserialize("DataSourceCreated", payload)

        assert isinstance(event, DataSourceCreated)
        assert event.data_source_id == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert event.adapter_type == "github"
        assert event.created_by is None

    def test_raises_for_unknown_event_type(self):
        """Deserializer should raise for unknown event types."""
        serializer = ManagementEventSerializer()

        with pytest.raises(ValueError, match="Unsupported event type"):
            serializer.deserialize("UnknownEvent", {})


class TestRoundTrip:
    """Test serialize -> deserialize round trip."""

    def test_round_trip_all_events(self):
        """All event types should round trip correctly."""
        serializer = ManagementEventSerializer()
        occurred_at = datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)
        events: list[DomainEvent] = [
            KnowledgeGraphCreated(
                knowledge_graph_id="kg-1",
                tenant_id="tenant-1",
                workspace_id="ws-1",
                name="Graph One",
                description="First graph",
                occurred_at=occurred_at,
                created_by="user-1",
            ),
            KnowledgeGraphUpdated(
                knowledge_graph_id="kg-1",
                tenant_id="tenant-1",
                name="Updated Graph",
                description="Updated description",
                occurred_at=occurred_at,
                updated_by="user-1",
            ),
            KnowledgeGraphDeleted(
                knowledge_graph_id="kg-1",
                tenant_id="tenant-1",
                workspace_id="ws-1",
                occurred_at=occurred_at,
                deleted_by="user-1",
            ),
            DataSourceCreated(
                data_source_id="ds-1",
                knowledge_graph_id="kg-1",
                tenant_id="tenant-1",
                name="GitHub Source",
                adapter_type="github",
                occurred_at=occurred_at,
                created_by="user-1",
            ),
            DataSourceUpdated(
                data_source_id="ds-1",
                knowledge_graph_id="kg-1",
                tenant_id="tenant-1",
                name="Updated Source",
                occurred_at=occurred_at,
                updated_by="user-1",
            ),
            DataSourceDeleted(
                data_source_id="ds-1",
                knowledge_graph_id="kg-1",
                tenant_id="tenant-1",
                occurred_at=occurred_at,
                deleted_by="user-1",
            ),
            SyncStarted(
                sync_run_id="run-1",
                data_source_id="ds-1",
                knowledge_graph_id="kg-1",
                tenant_id="tenant-1",
                adapter_type="github",
                connection_config={"repo": "org/repo"},
                credentials_path=None,
                occurred_at=occurred_at,
                requested_by="user-1",
            ),
        ]

        for original in events:
            event_type = type(original).__name__
            payload = serializer.serialize(original)
            restored = serializer.deserialize(event_type, payload)
            assert restored == original, f"Round trip failed for {event_type}"

    def test_round_trip_with_none_optional_fields(self):
        """Events with None optional fields should round trip correctly."""
        serializer = ManagementEventSerializer()
        occurred_at = datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)

        original = KnowledgeGraphCreated(
            knowledge_graph_id="kg-1",
            tenant_id="tenant-1",
            workspace_id="ws-1",
            name="Graph",
            description="",
            occurred_at=occurred_at,
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("KnowledgeGraphCreated", payload)

        assert restored == original
        assert restored.created_by is None
