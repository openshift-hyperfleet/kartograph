"""SyncSchedulerService: triggers scheduled syncs for data sources.

This service implements the scheduled trigger scenario from the sync lifecycle spec.
It periodically checks data sources with CRON or INTERVAL schedules and initiates
syncs that are due, as if they were manually triggered.

The service is designed to be called by a background task (e.g., an asyncio task
started at application startup) at a configurable polling interval.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from croniter import CroniterBadCronError, croniter

from management.domain.aggregates import DataSource
from management.domain.entities.data_source_sync_run import DataSourceSyncRun
from management.domain.value_objects import ScheduleType

if TYPE_CHECKING:
    from management.ports.repositories import (
        IDataSourceRepository,
        IDataSourceSyncRunRepository,
    )


# ISO 8601 duration pattern (subset: supports P[n]D and PT[n]H[n]M[n]S)
_ISO8601_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def _parse_iso8601_duration(value: str) -> timedelta:
    """Parse an ISO 8601 duration string into a timedelta.

    Supports the common forms:
    - P1D          → 1 day
    - PT1H         → 1 hour
    - PT30M        → 30 minutes
    - PT1H30M      → 1.5 hours
    - PT24H        → 24 hours
    - P1DT2H30M    → 26.5 hours

    Args:
        value: ISO 8601 duration string

    Returns:
        timedelta equivalent

    Raises:
        ValueError: If the duration string cannot be parsed
    """
    match = _ISO8601_DURATION_RE.match(value)
    if not match:
        raise ValueError(
            f"Invalid ISO 8601 duration: {value!r}. "
            "Expected format like 'PT1H', 'PT30M', 'P1D', 'P1DT2H'."
        )

    days = float(match.group("days") or 0)
    hours = float(match.group("hours") or 0)
    minutes = float(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0)

    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds

    if total_seconds <= 0:
        raise ValueError(f"Duration must be positive, got: {value!r}")

    return timedelta(seconds=total_seconds)


class SyncSchedulerService:
    """Application service that triggers scheduled syncs for data sources.

    This service polls data sources with CRON or INTERVAL schedules and
    initiates syncs that are due. It is intended to be called periodically
    by a background task.

    Spec: GIVEN a data source with a CRON or INTERVAL schedule,
    WHEN the schedule fires,
    THEN a sync is initiated as if manually triggered.

    Args:
        data_source_repository: Repository for reading data source metadata
        sync_run_repository: Repository for creating sync run records
    """

    def __init__(
        self,
        data_source_repository: "IDataSourceRepository",
        sync_run_repository: "IDataSourceSyncRunRepository",
    ) -> None:
        self._ds_repo = data_source_repository
        self._sync_run_repo = sync_run_repository

    async def check_and_trigger_due_syncs(
        self,
        now: datetime | None = None,
    ) -> int:
        """Check all data sources and trigger any that are due for a scheduled sync.

        For INTERVAL schedules: a sync is due if the elapsed time since the
        last sync (or all time if never synced) exceeds the interval duration.

        For CRON schedules: a sync is due if the most recent cron fire time
        since the last sync has passed.  Uses ``croniter`` to evaluate the
        expression against the current time.

        Args:
            now: The current time for comparison (defaults to UTC now).
                 Parameterized for testability.

        Returns:
            Number of syncs triggered
        """
        if now is None:
            now = datetime.now(UTC)

        data_sources = await self._ds_repo.find_all()
        triggered = 0

        for ds in data_sources:
            if ds.schedule.schedule_type == ScheduleType.MANUAL:
                continue

            if ds.schedule.schedule_type == ScheduleType.INTERVAL:
                if self._is_interval_due(ds.schedule.value, ds.last_sync_at, now):
                    await self._trigger_sync(ds, now)
                    triggered += 1

            elif ds.schedule.schedule_type == ScheduleType.CRON:
                if self._is_cron_due(ds.schedule.value, ds.last_sync_at, now):
                    await self._trigger_sync(ds, now)
                    triggered += 1

        return triggered

    def _is_interval_due(
        self,
        schedule_value: str | None,
        last_sync_at: datetime | None,
        now: datetime,
    ) -> bool:
        """Determine if an INTERVAL schedule is due for a sync.

        Args:
            schedule_value: ISO 8601 duration string (e.g., "PT1H")
            last_sync_at: When the data source last completed a sync
            now: Current time

        Returns:
            True if the interval has elapsed since the last sync (or if
            the data source has never been synced)
        """
        if schedule_value is None:
            return False

        try:
            interval = _parse_iso8601_duration(schedule_value)
        except ValueError:
            # Invalid interval — skip to avoid crashing the scheduler
            return False

        if last_sync_at is None:
            # Never synced — trigger immediately
            return True

        return now >= last_sync_at + interval

    def _is_cron_due(
        self,
        schedule_value: str | None,
        last_sync_at: datetime | None,
        now: datetime,
    ) -> bool:
        """Determine if a CRON schedule is due for a sync.

        A CRON schedule is due when its most recent fire time (the last time
        the expression would have fired at or before ``now``) is strictly after
        ``last_sync_at``.  If the source has never been synced (``last_sync_at``
        is ``None``) the schedule is always considered due.

        Args:
            schedule_value: Standard 5-field cron expression (e.g. ``"0 * * * *"``)
            last_sync_at: When the data source last completed a sync
            now: Current time (UTC-aware)

        Returns:
            ``True`` if a sync should be triggered, ``False`` otherwise.
        """
        if schedule_value is None:
            return False

        try:
            if not croniter.is_valid(schedule_value):
                return False

            # croniter.get_prev() returns the most recent fire time *at or before*
            # `now`.  We pass `now` as the start so the first call to get_prev
            # walks back to find the previous fire time.
            itr = croniter(schedule_value, now)
            last_fire: datetime = itr.get_prev(datetime)

            # croniter returns a naive datetime; normalise to UTC if the input
            # datetimes are timezone-aware.
            if now.tzinfo is not None and last_fire.tzinfo is None:
                last_fire = last_fire.replace(tzinfo=UTC)

        except (CroniterBadCronError, ValueError):
            # Invalid expression — skip rather than crashing the scheduler.
            return False

        if last_sync_at is None:
            # The source has never been synced → always due.
            return True

        # Normalise last_sync_at to naive UTC for comparison when needed.
        normalised_last_sync = last_sync_at
        if last_sync_at.tzinfo is not None and last_fire.tzinfo is None:
            normalised_last_sync = last_sync_at.replace(tzinfo=None)

        return last_fire > normalised_last_sync

    async def _trigger_sync(self, ds: DataSource, now: datetime) -> None:
        """Create a sync run record and emit SyncStarted event.

        This mirrors what DataSourceService.trigger_sync() does, but
        without the authorization check (the scheduler is a trusted
        internal service, not acting on behalf of a user).

        Args:
            ds: The DataSource aggregate to trigger
            now: The current time (used for sync run timestamps)
        """
        from ulid import ULID

        sync_run_id = str(ULID())

        sync_run = DataSourceSyncRun(
            id=sync_run_id,
            data_source_id=ds.id.value,
            status="pending",
            started_at=now,
            completed_at=None,
            error=None,
            created_at=now,
        )
        await self._sync_run_repo.save(sync_run)

        # Emit SyncStarted event via data source aggregate
        ds.request_sync(sync_run_id=sync_run_id, requested_by="scheduler")
        await self._ds_repo.save(ds)
