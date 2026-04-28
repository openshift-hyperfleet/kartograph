"""Unit tests for SyncSchedulerService.

Tests that data sources with due CRON or INTERVAL schedules are
triggered as scheduled syncs.

Spec coverage:
- Requirement: Sync Initiation
- Scenario: Scheduled trigger
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from management.application.services.sync_scheduler import SyncSchedulerService
from management.domain.aggregates.data_source import DataSource
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from shared_kernel.datasource_types import DataSourceAdapterType


def _make_data_source(
    ds_id: str = "ds-001",
    schedule_type: ScheduleType = ScheduleType.INTERVAL,
    schedule_value: str | None = "PT1H",
    last_sync_at: datetime | None = None,
) -> DataSource:
    """Create a test DataSource aggregate."""
    now = datetime.now(UTC)
    return DataSource(
        id=DataSourceId(value=ds_id),
        knowledge_graph_id="kg-001",
        tenant_id="tenant-001",
        name=f"Data Source {ds_id}",
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"repo": "org/repo"},
        credentials_path=None,
        schedule=Schedule(schedule_type=schedule_type, value=schedule_value),
        last_sync_at=last_sync_at,
        created_at=now,
        updated_at=now,
    )


class _FakeDataSourceRepository:
    """Fake data source repository."""

    def __init__(self, data_sources: list[DataSource]) -> None:
        self._data_sources = data_sources
        self.saved: list[DataSource] = []

    async def find_all(self) -> list[DataSource]:
        return list(self._data_sources)

    async def save(self, data_source: DataSource) -> None:
        self.saved.append(data_source)

    async def get_by_id(self, data_source_id: DataSourceId) -> DataSource | None:
        for ds in self._data_sources:
            if ds.id == data_source_id:
                return ds
        return None

    async def find_by_knowledge_graph(
        self, knowledge_graph_id: str
    ) -> list[DataSource]:
        return [
            ds
            for ds in self._data_sources
            if ds.knowledge_graph_id == knowledge_graph_id
        ]

    async def delete(self, data_source: DataSource) -> bool:
        return True


class _FakeSyncRunRepository:
    """Fake sync run repository that captures saved sync runs."""

    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, sync_run: Any) -> None:
        self.saved.append(sync_run)

    async def get_by_id(self, sync_run_id: str) -> Any | None:
        return None

    async def find_by_data_source(self, data_source_id: str) -> list[Any]:
        return []


class _FakeDataSourceRepositoryWithSave(_FakeDataSourceRepository):
    """Fake data source repository that tracks saves after sync triggering."""

    def __init__(self, data_sources: list[DataSource]) -> None:
        super().__init__(data_sources)
        # Track updates from trigger_sync path
        self._data_sources_by_id = {ds.id.value: ds for ds in data_sources}

    async def save(self, data_source: DataSource) -> None:
        self.saved.append(data_source)
        self._data_sources_by_id[data_source.id.value] = data_source


@pytest.fixture
def now() -> datetime:
    return datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


class TestSyncSchedulerServiceIntervalSchedule:
    """Tests for INTERVAL schedule triggering.

    Spec: GIVEN a data source with an INTERVAL schedule,
    WHEN the schedule fires, THEN a sync is initiated.
    """

    @pytest.mark.asyncio
    async def test_triggers_interval_sync_when_never_synced(self, now: datetime):
        """Data source with INTERVAL schedule and no prior sync should be triggered."""
        ds = _make_data_source(
            ds_id="ds-001",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT1H",
            last_sync_at=None,  # Never synced
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 1
        assert len(run_repo.saved) == 1
        assert run_repo.saved[0].data_source_id == "ds-001"
        assert run_repo.saved[0].status == "pending"

    @pytest.mark.asyncio
    async def test_triggers_interval_sync_when_interval_elapsed(self, now: datetime):
        """Data source should be triggered when interval has elapsed since last sync."""
        last_sync_at = now - timedelta(
            hours=2
        )  # Synced 2 hours ago, interval is 1 hour
        ds = _make_data_source(
            ds_id="ds-001",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT1H",
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 1

    @pytest.mark.asyncio
    async def test_does_not_trigger_when_interval_not_elapsed(self, now: datetime):
        """Data source should NOT be triggered when interval has not yet elapsed."""
        last_sync_at = now - timedelta(
            minutes=30
        )  # Synced 30 min ago, interval is 1 hour
        ds = _make_data_source(
            ds_id="ds-001",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT1H",
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 0
        assert len(run_repo.saved) == 0

    @pytest.mark.asyncio
    async def test_skips_manual_schedule(self, now: datetime):
        """Data sources with MANUAL schedule should never be triggered by scheduler."""
        ds = _make_data_source(
            ds_id="ds-001",
            schedule_type=ScheduleType.MANUAL,
            schedule_value=None,
            last_sync_at=None,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 0
        assert len(run_repo.saved) == 0

    @pytest.mark.asyncio
    async def test_triggers_multiple_due_data_sources(self, now: datetime):
        """Multiple data sources due for sync should all be triggered."""
        ds1 = _make_data_source(
            ds_id="ds-001",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT1H",
            last_sync_at=now - timedelta(hours=2),
        )
        ds2 = _make_data_source(
            ds_id="ds-002",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT30M",
            last_sync_at=now - timedelta(hours=1),
        )
        ds3 = _make_data_source(
            ds_id="ds-003",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT2H",
            last_sync_at=now - timedelta(minutes=30),  # Not due yet
        )

        ds_repo = _FakeDataSourceRepository([ds1, ds2, ds3])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 2
        triggered_ids = {run.data_source_id for run in run_repo.saved}
        assert "ds-001" in triggered_ids
        assert "ds-002" in triggered_ids
        assert "ds-003" not in triggered_ids

    @pytest.mark.asyncio
    async def test_triggered_sync_run_has_pending_status(self, now: datetime):
        """Triggered sync runs should start with 'pending' status."""
        ds = _make_data_source(
            ds_id="ds-001",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT1H",
            last_sync_at=None,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        await scheduler.check_and_trigger_due_syncs(now=now)

        sync_run = run_repo.saved[0]
        assert sync_run.status == "pending"
        assert sync_run.data_source_id == "ds-001"
        assert sync_run.id is not None

    @pytest.mark.asyncio
    async def test_sync_started_event_emitted(self, now: datetime):
        """Triggering a sync should publish a SyncStarted event via data source save."""
        ds = _make_data_source(
            ds_id="ds-001",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT1H",
            last_sync_at=None,
        )
        ds_repo = _FakeDataSourceRepositoryWithSave([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        await scheduler.check_and_trigger_due_syncs(now=now)

        # The data source should have been saved (which publishes SyncStarted via outbox)
        assert len(ds_repo.saved) >= 1


class TestSyncSchedulerIntervalParsing:
    """Tests for ISO 8601 interval duration parsing."""

    @pytest.mark.asyncio
    async def test_parses_pt30m_interval(self):
        """PT30M should be parsed as 30 minutes."""
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        last_sync_at = now - timedelta(minutes=31)  # 31 min ago, 30 min interval

        ds = _make_data_source(
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT30M",
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)
        assert count == 1

    @pytest.mark.asyncio
    async def test_parses_pt24h_interval(self):
        """PT24H should be parsed as 24 hours."""
        now = datetime(2024, 6, 2, 12, 0, 0, tzinfo=UTC)
        last_sync_at = datetime(2024, 6, 1, 10, 0, 0, tzinfo=UTC)  # 26 hours ago

        ds = _make_data_source(
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="PT24H",
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)
        assert count == 1

    @pytest.mark.asyncio
    async def test_parses_p1d_interval(self):
        """P1D should be parsed as 1 day (24 hours)."""
        now = datetime(2024, 6, 2, 12, 0, 0, tzinfo=UTC)
        last_sync_at = datetime(2024, 6, 1, 10, 0, 0, tzinfo=UTC)  # 26 hours ago

        ds = _make_data_source(
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="P1D",
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)
        assert count == 1


class TestSyncSchedulerCronSchedule:
    """Tests for CRON schedule triggering.

    Spec: GIVEN a data source with a CRON schedule,
    WHEN the schedule fires, THEN a sync is initiated as if manually triggered.
    """

    @pytest.mark.asyncio
    async def test_triggers_cron_sync_when_never_synced(self):
        """Data source with CRON schedule and no prior sync should be triggered."""
        # CRON fires every hour on the hour; now is 12:05
        now = datetime(2024, 6, 1, 12, 5, 0, tzinfo=UTC)
        ds = _make_data_source(
            ds_id="ds-cron-001",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 * * * *",  # Every hour
            last_sync_at=None,  # Never synced
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 1
        assert len(run_repo.saved) == 1
        assert run_repo.saved[0].data_source_id == "ds-cron-001"
        assert run_repo.saved[0].status == "pending"

    @pytest.mark.asyncio
    async def test_triggers_cron_sync_when_cron_fired_since_last_sync(self):
        """Trigger when CRON has fired at least once since last_sync_at."""
        # Now is 12:05, CRON last fired at 12:00, last sync was at 11:30
        # → The 12:00 fire is newer than 11:30 → trigger
        now = datetime(2024, 6, 1, 12, 5, 0, tzinfo=UTC)
        last_sync_at = datetime(2024, 6, 1, 11, 30, 0, tzinfo=UTC)

        ds = _make_data_source(
            ds_id="ds-cron-002",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 * * * *",  # Every hour on the hour
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 1

    @pytest.mark.asyncio
    async def test_does_not_trigger_cron_when_synced_after_last_fire(self):
        """Do NOT trigger when last sync happened after the CRON's most recent fire."""
        # Now is 12:05, CRON last fired at 12:00, last sync was at 12:02
        # → The 12:00 fire is older than 12:02 → do NOT trigger
        now = datetime(2024, 6, 1, 12, 5, 0, tzinfo=UTC)
        last_sync_at = datetime(2024, 6, 1, 12, 2, 0, tzinfo=UTC)

        ds = _make_data_source(
            ds_id="ds-cron-003",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 * * * *",  # Every hour on the hour
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 0
        assert len(run_repo.saved) == 0

    @pytest.mark.asyncio
    async def test_triggers_cron_daily_schedule(self):
        """Test a daily CRON expression (0 0 * * *)."""
        # Now is 2024-06-02 08:00, daily CRON last fired at 2024-06-02 00:00
        # Last sync was 2024-06-01 02:00 (before yesterday's midnight fire)
        # The midnight fire on 2024-06-02 is newer than last sync → trigger
        now = datetime(2024, 6, 2, 8, 0, 0, tzinfo=UTC)
        last_sync_at = datetime(2024, 6, 1, 2, 0, 0, tzinfo=UTC)

        ds = _make_data_source(
            ds_id="ds-cron-004",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 0 * * *",  # Every day at midnight
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        assert count == 1

    @pytest.mark.asyncio
    async def test_does_not_trigger_cron_before_first_fire(self):
        """Do NOT trigger when CRON has not yet fired (now is before the first fire time)."""
        # CRON: 0 15 * * * (fires at 15:00 each day)
        # Now is 14:30 — the CRON has not yet fired today; last_sync_at is None
        # The most recent fire is yesterday at 15:00, but since last_sync_at is None
        # and the source was never synced, it SHOULD trigger.
        # Reframe: test that if now is exactly at a cron boundary it fires correctly.
        # Actually let's test: now is 11:59, CRON is "0 12 * * *" (noon), last sync = 11:58
        # The previous fire is yesterday noon → older than last_sync_at → skip
        now = datetime(2024, 6, 1, 11, 59, 0, tzinfo=UTC)
        last_sync_at = datetime(2024, 6, 1, 11, 58, 0, tzinfo=UTC)

        ds = _make_data_source(
            ds_id="ds-cron-005",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 12 * * *",  # Every day at noon
            last_sync_at=last_sync_at,
        )
        ds_repo = _FakeDataSourceRepository([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        count = await scheduler.check_and_trigger_due_syncs(now=now)

        # The last fire was yesterday at noon (2024-05-31 12:00), which is BEFORE
        # last_sync_at (2024-06-01 11:58). The next fire (today noon) hasn't happened yet.
        assert count == 0

    @pytest.mark.asyncio
    async def test_cron_sync_emits_sync_started_event(self):
        """Triggering a CRON sync should publish a SyncStarted event via data source save."""
        now = datetime(2024, 6, 1, 12, 5, 0, tzinfo=UTC)
        ds = _make_data_source(
            ds_id="ds-cron-006",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 * * * *",  # Every hour
            last_sync_at=None,
        )
        ds_repo = _FakeDataSourceRepositoryWithSave([ds])
        run_repo = _FakeSyncRunRepository()

        scheduler = SyncSchedulerService(
            data_source_repository=ds_repo,
            sync_run_repository=run_repo,
        )

        await scheduler.check_and_trigger_due_syncs(now=now)

        # The data source should have been saved (which publishes SyncStarted via outbox)
        assert len(ds_repo.saved) >= 1
