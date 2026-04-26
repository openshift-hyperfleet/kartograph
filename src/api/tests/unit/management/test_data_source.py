"""Unit tests for DataSource aggregate."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from management.domain.aggregates.data_source import DataSource
from management.domain.events import (
    DataSourceCreated,
    DataSourceDeleted,
    DataSourceSyncRequested,
    DataSourceUpdated,
)
from management.domain.exceptions import (
    AggregateDeletedError,
    InvalidDataSourceNameError,
    InvalidIdentifierError,
)
from management.domain.observability import DataSourceProbe
from management.domain.value_objects import (
    DataSourceId,
    Schedule,
    ScheduleType,
)
from shared_kernel.datasource_types import DataSourceAdapterType


class TestDataSourceCreate:
    """Tests for DataSource.create() factory method."""

    def test_create_sets_all_fields(self):
        """create() should set all fields correctly."""
        ds = DataSource.create(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            name="GitHub Repo",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo", "branch": "main"},
        )
        assert isinstance(ds.id, DataSourceId)
        assert ds.knowledge_graph_id == "kg-123"
        assert ds.tenant_id == "tenant-456"
        assert ds.name == "GitHub Repo"
        assert ds.adapter_type == DataSourceAdapterType.GITHUB
        assert ds.connection_config == {"repo": "org/repo", "branch": "main"}
        assert isinstance(ds.created_at, datetime)
        assert isinstance(ds.updated_at, datetime)
        assert ds.created_at == ds.updated_at

    def test_create_generates_unique_id(self):
        """Each create() call should generate a unique ID."""
        ds1 = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source 1",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        ds2 = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source 2",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        assert ds1.id != ds2.id

    def test_create_emits_data_source_created_event(self):
        """create() should emit a DataSourceCreated event with correct primitive fields."""
        ds = DataSource.create(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            name="GitHub Repo",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
            created_by="user-abc",
        )
        events = ds.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, DataSourceCreated)
        assert event.data_source_id == ds.id.value
        assert event.knowledge_graph_id == "kg-123"
        assert event.tenant_id == "tenant-456"
        assert event.name == "GitHub Repo"
        assert event.adapter_type == "github"
        assert event.created_by == "user-abc"
        assert isinstance(event.occurred_at, datetime)

    def test_create_without_actor(self):
        """create() without created_by should set it to None in event."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        events = ds.collect_events()
        assert events[0].created_by is None

    def test_create_calls_probe(self):
        """create() should call the probe's created method with correct args."""
        probe = MagicMock(spec=DataSourceProbe)
        ds = DataSource.create(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            name="GitHub Repo",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
            probe=probe,
        )
        probe.created.assert_called_once_with(
            data_source_id=ds.id.value,
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            name="GitHub Repo",
            adapter_type="github",
        )

    def test_create_sets_default_manual_schedule(self):
        """create() should default schedule to Schedule(MANUAL)."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        assert ds.schedule == Schedule(schedule_type=ScheduleType.MANUAL)

    def test_create_sets_last_sync_at_to_none(self):
        """create() should set last_sync_at to None (no sync has happened yet)."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        assert ds.last_sync_at is None

    def test_create_with_credentials_path(self):
        """create() should store optional credentials_path."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
            credentials_path="vault/secrets/github-token",
        )
        assert ds.credentials_path == "vault/secrets/github-token"

    def test_create_without_credentials_path(self):
        """create() without credentials_path should default to None."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        assert ds.credentials_path is None

    def test_create_defensively_copies_connection_config(self):
        """create() should copy connection_config to avoid external mutation."""
        original_config = {"repo": "org/repo"}
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config=original_config,
        )
        original_config["injected"] = "evil"
        assert "injected" not in ds.connection_config


class TestDataSourceUpdateConnection:
    """Tests for DataSource.update_connection() method."""

    def _create_ds(self, **kwargs):
        """Helper to create a DataSource and clear creation events."""
        defaults = {
            "knowledge_graph_id": "kg-123",
            "tenant_id": "tenant-456",
            "name": "Original Source",
            "adapter_type": DataSourceAdapterType.GITHUB,
            "connection_config": {"repo": "org/repo"},
        }
        defaults.update(kwargs)
        ds = DataSource.create(**defaults)
        ds.collect_events()  # clear creation event
        return ds

    def test_update_connection_changes_fields(self):
        """update_connection() should update name, connection_config, and credentials_path."""
        ds = self._create_ds()
        ds.update_connection(
            name="Updated Source",
            connection_config={"repo": "org/new-repo", "branch": "dev"},
            credentials_path="vault/secrets/new-token",
        )
        assert ds.name == "Updated Source"
        assert ds.connection_config == {"repo": "org/new-repo", "branch": "dev"}
        assert ds.credentials_path == "vault/secrets/new-token"

    def test_update_connection_advances_updated_at(self):
        """update_connection() should advance the updated_at timestamp."""
        ds = self._create_ds()
        original_updated_at = ds.updated_at
        ds.update_connection(
            name="Updated",
            connection_config={"repo": "org/repo"},
            credentials_path=None,
        )
        assert ds.updated_at >= original_updated_at

    def test_update_connection_emits_data_source_updated_event(self):
        """update_connection() should emit a DataSourceUpdated event with correct fields."""
        ds = self._create_ds()
        ds.update_connection(
            name="Updated Source",
            connection_config={"repo": "org/new-repo"},
            credentials_path=None,
            updated_by="user-xyz",
        )
        events = ds.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, DataSourceUpdated)
        assert event.data_source_id == ds.id.value
        assert event.knowledge_graph_id == ds.knowledge_graph_id
        assert event.tenant_id == ds.tenant_id
        assert event.name == "Updated Source"
        assert event.updated_by == "user-xyz"

    def test_update_connection_with_actor(self):
        """update_connection() should include updated_by when provided."""
        ds = self._create_ds()
        ds.update_connection(
            name="Updated",
            connection_config={},
            credentials_path=None,
            updated_by="user-abc",
        )
        events = ds.collect_events()
        assert events[0].updated_by == "user-abc"

    def test_update_connection_without_actor(self):
        """update_connection() without updated_by should set it to None in event."""
        ds = self._create_ds()
        ds.update_connection(
            name="Updated",
            connection_config={},
            credentials_path=None,
        )
        events = ds.collect_events()
        assert events[0].updated_by is None

    def test_update_connection_calls_probe(self):
        """update_connection() should call the probe's updated method."""
        probe = MagicMock(spec=DataSourceProbe)
        ds = self._create_ds(probe=probe)
        probe.reset_mock()
        ds.update_connection(
            name="Updated Source",
            connection_config={"repo": "org/new-repo"},
            credentials_path=None,
        )
        probe.updated.assert_called_once_with(
            data_source_id=ds.id.value,
            knowledge_graph_id=ds.knowledge_graph_id,
            tenant_id=ds.tenant_id,
            name="Updated Source",
        )

    def test_update_connection_defensively_copies_connection_config(self):
        """update_connection() should copy connection_config to avoid external mutation."""
        ds = self._create_ds()
        new_config = {"repo": "org/new-repo"}
        ds.update_connection(
            name="Updated",
            connection_config=new_config,
            credentials_path=None,
        )
        new_config["injected"] = "evil"
        assert "injected" not in ds.connection_config

    def test_update_connection_raises_after_deletion(self):
        """update_connection() should raise AggregateDeletedError after mark_for_deletion()."""
        ds = self._create_ds()
        ds.mark_for_deletion()
        ds.collect_events()
        with pytest.raises(AggregateDeletedError):
            ds.update_connection(
                name="Should fail", connection_config={}, credentials_path=None
            )


class TestDataSourceRequestSync:
    """Tests for DataSource.request_sync() method."""

    def _create_ds(self, **kwargs):
        """Helper to create a DataSource and clear creation events."""
        defaults = {
            "knowledge_graph_id": "kg-123",
            "tenant_id": "tenant-456",
            "name": "Source",
            "adapter_type": DataSourceAdapterType.GITHUB,
            "connection_config": {},
        }
        defaults.update(kwargs)
        ds = DataSource.create(**defaults)
        ds.collect_events()
        return ds

    def test_request_sync_emits_sync_requested_event(self):
        """request_sync() should emit a DataSourceSyncRequested event."""
        ds = self._create_ds()
        ds.request_sync(requested_by="user-abc")
        events = ds.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, DataSourceSyncRequested)
        assert event.data_source_id == ds.id.value
        assert event.knowledge_graph_id == "kg-123"
        assert event.tenant_id == "tenant-456"
        assert event.requested_by == "user-abc"
        assert event.occurred_at is not None

    def test_request_sync_without_actor(self):
        """request_sync() without requested_by should set it to None."""
        ds = self._create_ds()
        ds.request_sync()
        events = ds.collect_events()
        assert events[0].requested_by is None

    def test_request_sync_raises_after_deletion(self):
        """request_sync() should raise AggregateDeletedError after mark_for_deletion()."""
        ds = self._create_ds()
        ds.mark_for_deletion()
        ds.collect_events()
        with pytest.raises(AggregateDeletedError):
            ds.request_sync()


class TestDataSourceUpdateSchedule:
    """Tests for DataSource.update_schedule() method."""

    def _create_ds(self, **kwargs):
        """Helper to create a DataSource and clear creation events."""
        defaults = {
            "knowledge_graph_id": "kg-123",
            "tenant_id": "tenant-456",
            "name": "Source",
            "adapter_type": DataSourceAdapterType.GITHUB,
            "connection_config": {},
        }
        defaults.update(kwargs)
        ds = DataSource.create(**defaults)
        ds.collect_events()
        return ds

    def test_update_schedule_changes_schedule(self):
        """update_schedule() should update the schedule value object."""
        ds = self._create_ds()
        assert ds.schedule == Schedule(schedule_type=ScheduleType.MANUAL)
        new_schedule = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        ds.update_schedule(new_schedule)
        assert ds.schedule == new_schedule

    def test_update_schedule_emits_data_source_updated_event(self):
        """update_schedule() should emit a DataSourceUpdated event."""
        ds = self._create_ds()
        new_schedule = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        ds.update_schedule(new_schedule, updated_by="user-abc")
        events = ds.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, DataSourceUpdated)
        assert event.data_source_id == ds.id.value
        assert event.updated_by == "user-abc"

    def test_update_schedule_advances_updated_at(self):
        """update_schedule() should advance the updated_at timestamp."""
        ds = self._create_ds()
        original_updated_at = ds.updated_at
        new_schedule = Schedule(schedule_type=ScheduleType.INTERVAL, value="PT1H")
        ds.update_schedule(new_schedule)
        assert ds.updated_at >= original_updated_at

    def test_update_schedule_calls_probe(self):
        """update_schedule() should call the probe's updated method."""
        probe = MagicMock(spec=DataSourceProbe)
        ds = self._create_ds(probe=probe)
        probe.reset_mock()
        new_schedule = Schedule(schedule_type=ScheduleType.CRON, value="*/5 * * * *")
        ds.update_schedule(new_schedule)
        probe.updated.assert_called_once_with(
            data_source_id=ds.id.value,
            knowledge_graph_id=ds.knowledge_graph_id,
            tenant_id=ds.tenant_id,
            name=ds.name,
        )

    def test_update_schedule_raises_after_deletion(self):
        """update_schedule() should raise AggregateDeletedError after mark_for_deletion()."""
        ds = self._create_ds()
        ds.mark_for_deletion()
        ds.collect_events()
        with pytest.raises(AggregateDeletedError):
            ds.update_schedule(Schedule(schedule_type=ScheduleType.MANUAL))

    def test_update_schedule_to_interval(self):
        """update_schedule() should support INTERVAL schedule type."""
        ds = self._create_ds()
        interval_schedule = Schedule(schedule_type=ScheduleType.INTERVAL, value="PT30M")
        ds.update_schedule(interval_schedule)
        assert ds.schedule.schedule_type == ScheduleType.INTERVAL
        assert ds.schedule.value == "PT30M"

    def test_update_schedule_back_to_manual(self):
        """update_schedule() should support reverting to MANUAL schedule."""
        ds = self._create_ds()
        # First set to cron
        ds.update_schedule(Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *"))
        ds.collect_events()
        # Then back to manual
        ds.update_schedule(Schedule(schedule_type=ScheduleType.MANUAL))
        assert ds.schedule.schedule_type == ScheduleType.MANUAL
        assert ds.schedule.value is None


class TestDataSourceRecordSyncCompleted:
    """Tests for DataSource.record_sync_completed() method."""

    def _create_ds(self, **kwargs):
        """Helper to create a DataSource and clear creation events."""
        defaults = {
            "knowledge_graph_id": "kg-123",
            "tenant_id": "tenant-456",
            "name": "Source",
            "adapter_type": DataSourceAdapterType.GITHUB,
            "connection_config": {},
        }
        defaults.update(kwargs)
        ds = DataSource.create(**defaults)
        ds.collect_events()
        return ds

    def test_record_sync_completed_sets_last_sync_at(self):
        """record_sync_completed() should set last_sync_at to current time."""
        ds = self._create_ds()
        assert ds.last_sync_at is None
        before = datetime.now(UTC)
        ds.record_sync_completed()
        after = datetime.now(UTC)
        assert ds.last_sync_at is not None
        assert before <= ds.last_sync_at <= after

    def test_record_sync_completed_calls_probe(self):
        """record_sync_completed() should call the probe's sync_completed method."""
        probe = MagicMock(spec=DataSourceProbe)
        ds = self._create_ds(probe=probe)
        probe.reset_mock()
        ds.record_sync_completed()
        probe.sync_completed.assert_called_once_with(
            data_source_id=ds.id.value,
            knowledge_graph_id=ds.knowledge_graph_id,
            tenant_id=ds.tenant_id,
        )

    def test_record_sync_completed_does_not_emit_event(self):
        """record_sync_completed() should NOT emit any domain event."""
        ds = self._create_ds()
        ds.record_sync_completed()
        events = ds.collect_events()
        assert events == []

    def test_record_sync_completed_raises_after_deletion(self):
        """record_sync_completed() should raise AggregateDeletedError after mark_for_deletion()."""
        ds = self._create_ds()
        ds.mark_for_deletion()
        ds.collect_events()
        with pytest.raises(AggregateDeletedError):
            ds.record_sync_completed()


class TestDataSourceMarkForDeletion:
    """Tests for DataSource.mark_for_deletion() method."""

    def _create_ds(self, **kwargs):
        """Helper to create a DataSource and clear creation events."""
        defaults = {
            "knowledge_graph_id": "kg-123",
            "tenant_id": "tenant-456",
            "name": "Source",
            "adapter_type": DataSourceAdapterType.GITHUB,
            "connection_config": {},
        }
        defaults.update(kwargs)
        ds = DataSource.create(**defaults)
        ds.collect_events()
        return ds

    def test_mark_for_deletion_emits_deleted_event(self):
        """mark_for_deletion() should emit DataSourceDeleted event."""
        ds = self._create_ds()
        ds.mark_for_deletion()
        events = ds.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, DataSourceDeleted)
        assert event.data_source_id == ds.id.value
        assert event.knowledge_graph_id == "kg-123"
        assert event.tenant_id == "tenant-456"

    def test_mark_for_deletion_with_actor(self):
        """mark_for_deletion() should include deleted_by when provided."""
        ds = self._create_ds()
        ds.mark_for_deletion(deleted_by="user-abc")
        events = ds.collect_events()
        assert events[0].deleted_by == "user-abc"

    def test_mark_for_deletion_without_actor(self):
        """mark_for_deletion() without actor should set deleted_by to None."""
        ds = self._create_ds()
        ds.mark_for_deletion()
        events = ds.collect_events()
        assert events[0].deleted_by is None

    def test_mark_for_deletion_calls_probe(self):
        """mark_for_deletion() should call the probe's deleted method."""
        probe = MagicMock(spec=DataSourceProbe)
        ds = self._create_ds(probe=probe)
        probe.reset_mock()
        ds.mark_for_deletion()
        probe.deleted.assert_called_once_with(
            data_source_id=ds.id.value,
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
        )

    def test_mark_for_deletion_is_idempotent(self):
        """Calling mark_for_deletion() twice should only emit one event."""
        ds = self._create_ds()
        ds.mark_for_deletion()
        ds.mark_for_deletion()  # second call should be no-op
        events = ds.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], DataSourceDeleted)


class TestDataSourceCollectEvents:
    """Tests for DataSource.collect_events() method."""

    def test_collect_events_returns_pending_events(self):
        """collect_events() should return all pending events."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        events = ds.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], DataSourceCreated)

    def test_collect_events_clears_pending_events(self):
        """collect_events() should clear the pending events list."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        ds.collect_events()
        events = ds.collect_events()
        assert events == []

    def test_collect_events_returns_events_in_order(self):
        """collect_events() should return events in the order they were recorded."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        ds.update_connection(
            name="Updated",
            connection_config={"repo": "new"},
            credentials_path=None,
        )
        ds.mark_for_deletion()
        events = ds.collect_events()
        assert len(events) == 3
        assert isinstance(events[0], DataSourceCreated)
        assert isinstance(events[1], DataSourceUpdated)
        assert isinstance(events[2], DataSourceDeleted)


class TestDataSourceValidation:
    """Tests for DataSource name validation."""

    def test_create_rejects_empty_name(self):
        """create() should raise error for empty name."""
        with pytest.raises(InvalidDataSourceNameError):
            DataSource.create(
                knowledge_graph_id="kg-1",
                tenant_id="t",
                name="",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    def test_create_rejects_name_over_100_chars(self):
        """create() should raise error for name exceeding 100 characters."""
        with pytest.raises(InvalidDataSourceNameError):
            DataSource.create(
                knowledge_graph_id="kg-1",
                tenant_id="t",
                name="x" * 101,
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    def test_create_accepts_name_exactly_100_chars(self):
        """create() should accept name that is exactly 100 characters."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="x" * 100,
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        assert len(ds.name) == 100

    def test_create_accepts_single_char_name(self):
        """create() should accept single character name."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="A",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        assert ds.name == "A"

    def test_update_connection_rejects_empty_name(self):
        """update_connection() should raise error for empty name."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Valid",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        ds.collect_events()
        with pytest.raises(InvalidDataSourceNameError):
            ds.update_connection(name="", connection_config={}, credentials_path=None)

    def test_update_connection_rejects_name_over_100_chars(self):
        """update_connection() should raise error for name exceeding 100 characters."""
        ds = DataSource.create(
            knowledge_graph_id="kg-1",
            tenant_id="t",
            name="Valid",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )
        ds.collect_events()
        with pytest.raises(InvalidDataSourceNameError):
            ds.update_connection(
                name="x" * 101, connection_config={}, credentials_path=None
            )

    def test_post_init_rejects_empty_name(self):
        """Direct construction with empty name should raise."""
        with pytest.raises(InvalidDataSourceNameError):
            DataSource(
                id=DataSourceId.generate(),
                knowledge_graph_id="kg-1",
                tenant_id="t",
                name="",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
                credentials_path=None,
                schedule=Schedule(schedule_type=ScheduleType.MANUAL),
                last_sync_at=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_create_rejects_empty_tenant_id(self):
        """create() with empty tenant_id should raise."""
        with pytest.raises(InvalidIdentifierError):
            DataSource.create(
                knowledge_graph_id="kg-1",
                tenant_id="",
                name="Source",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    def test_create_rejects_whitespace_tenant_id(self):
        """create() with whitespace-only tenant_id should raise."""
        with pytest.raises(InvalidIdentifierError):
            DataSource.create(
                knowledge_graph_id="kg-1",
                tenant_id="   ",
                name="Source",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    def test_create_rejects_empty_knowledge_graph_id(self):
        """create() with empty knowledge_graph_id should raise."""
        with pytest.raises(InvalidIdentifierError):
            DataSource.create(
                knowledge_graph_id="",
                tenant_id="t",
                name="Source",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    def test_create_rejects_whitespace_knowledge_graph_id(self):
        """create() with whitespace-only knowledge_graph_id should raise."""
        with pytest.raises(InvalidIdentifierError):
            DataSource.create(
                knowledge_graph_id="   ",
                tenant_id="t",
                name="Source",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )
