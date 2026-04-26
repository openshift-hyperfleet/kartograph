"""Unit tests for SyncLifecycleHandler.

Tests verify each lifecycle event transitions the sync run to the correct status,
and that terminal states (completed, failed) cannot be transitioned further.

Spec coverage:
- Scenario: State transitions
- Scenario: Terminal states
- Scenario: Status updates
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from management.domain.entities.data_source_sync_run import DataSourceSyncRun
from management.infrastructure.sync_lifecycle_handler import SyncLifecycleHandler


def _make_sync_run(
    run_id: str = "run-001",
    ds_id: str = "ds-001",
    status: str = "pending",
) -> DataSourceSyncRun:
    now = datetime.now(UTC)
    return DataSourceSyncRun(
        id=run_id,
        data_source_id=ds_id,
        status=status,
        started_at=now,
        completed_at=None,
        error=None,
        created_at=now,
    )


@pytest.fixture
def mock_session():
    """Mock AsyncSession with begin() context manager."""
    session = MagicMock()

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    return session


@pytest.fixture
def mock_sync_run_repo():
    return AsyncMock()


@pytest.fixture
def mock_ds_repo():
    return AsyncMock()


@pytest.fixture
def handler(mock_session, mock_sync_run_repo, mock_ds_repo):
    return SyncLifecycleHandler(
        session=mock_session,
        sync_run_repository=mock_sync_run_repo,
        data_source_repository=mock_ds_repo,
    )


def _payload(
    sync_run_id: str = "run-001",
    data_source_id: str = "ds-001",
    **extra: Any,
) -> dict[str, Any]:
    base = {
        "sync_run_id": sync_run_id,
        "data_source_id": data_source_id,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    base.update(extra)
    return base


class TestSyncLifecycleHandlerSupportedEvents:
    """Tests for supported_event_types()."""

    def test_supports_all_lifecycle_events(self, handler: SyncLifecycleHandler):
        """Handler should support all 7 lifecycle events."""
        expected = {
            "SyncStarted",
            "JobPackageProduced",
            "IngestionFailed",
            "MutationLogProduced",
            "ExtractionFailed",
            "MutationsApplied",
            "MutationApplicationFailed",
        }
        assert handler.supported_event_types() == expected


@pytest.mark.asyncio
class TestSyncStartedTransition:
    """SyncStarted → status = ingesting."""

    async def test_sync_started_sets_ingesting(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """SyncStarted should transition sync run to 'ingesting'."""
        run = _make_sync_run(status="pending")
        mock_sync_run_repo.get_by_id.return_value = run

        await handler.handle("SyncStarted", _payload(sync_run_id=run.id))

        mock_sync_run_repo.save.assert_called_once()
        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.status == "ingesting"


@pytest.mark.asyncio
class TestJobPackageProducedTransition:
    """JobPackageProduced → status = ai_extracting."""

    async def test_job_package_produced_sets_ai_extracting(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """JobPackageProduced should transition to 'ai_extracting'."""
        run = _make_sync_run(status="ingesting")
        mock_sync_run_repo.get_by_id.return_value = run

        await handler.handle(
            "JobPackageProduced",
            _payload(
                sync_run_id=run.id,
                knowledge_graph_id="kg-001",
                job_package_id="pkg-001",
            ),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.status == "ai_extracting"


@pytest.mark.asyncio
class TestIngestionFailedTransition:
    """IngestionFailed → status = failed."""

    async def test_ingestion_failed_sets_failed(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """IngestionFailed should transition to 'failed' with error message."""
        run = _make_sync_run(status="ingesting")
        mock_sync_run_repo.get_by_id.return_value = run

        await handler.handle(
            "IngestionFailed",
            _payload(sync_run_id=run.id, error="adapter timeout"),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.status == "failed"
        assert saved_run.error == "adapter timeout"


@pytest.mark.asyncio
class TestMutationLogProducedTransition:
    """MutationLogProduced → status = applying."""

    async def test_mutation_log_produced_sets_applying(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """MutationLogProduced should transition to 'applying'."""
        run = _make_sync_run(status="ai_extracting")
        mock_sync_run_repo.get_by_id.return_value = run

        await handler.handle(
            "MutationLogProduced",
            _payload(
                sync_run_id=run.id,
                knowledge_graph_id="kg-001",
                mutation_log_id="log-001",
            ),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.status == "applying"


@pytest.mark.asyncio
class TestExtractionFailedTransition:
    """ExtractionFailed → status = failed."""

    async def test_extraction_failed_sets_failed(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """ExtractionFailed should transition to 'failed'."""
        run = _make_sync_run(status="ai_extracting")
        mock_sync_run_repo.get_by_id.return_value = run

        await handler.handle(
            "ExtractionFailed",
            _payload(sync_run_id=run.id, error="AI extraction failed"),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.status == "failed"
        assert saved_run.error == "AI extraction failed"


@pytest.mark.asyncio
class TestMutationsAppliedTransition:
    """MutationsApplied → status = completed, last_sync_at updated."""

    async def test_mutations_applied_sets_completed(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
        mock_ds_repo: AsyncMock,
    ):
        """MutationsApplied should transition to 'completed'."""
        from management.domain.aggregates import DataSource
        from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
        from shared_kernel.datasource_types import DataSourceAdapterType

        run = _make_sync_run(status="applying")
        mock_sync_run_repo.get_by_id.return_value = run

        now = datetime.now(UTC)
        ds = DataSource(
            id=DataSourceId(value="ds-001"),
            knowledge_graph_id="kg-001",
            tenant_id="tenant-001",
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
            credentials_path=None,
            schedule=Schedule(schedule_type=ScheduleType.MANUAL),
            last_sync_at=None,
            created_at=now,
            updated_at=now,
        )
        mock_ds_repo.get_by_id.return_value = ds

        await handler.handle(
            "MutationsApplied",
            _payload(
                sync_run_id=run.id,
                knowledge_graph_id="kg-001",
            ),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.status == "completed"
        assert saved_run.completed_at is not None

    async def test_mutations_applied_updates_data_source_last_sync_at(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
        mock_ds_repo: AsyncMock,
    ):
        """MutationsApplied should update DataSource.last_sync_at."""
        from management.domain.aggregates import DataSource
        from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
        from shared_kernel.datasource_types import DataSourceAdapterType

        run = _make_sync_run(status="applying")
        mock_sync_run_repo.get_by_id.return_value = run

        now = datetime.now(UTC)
        ds = DataSource(
            id=DataSourceId(value="ds-001"),
            knowledge_graph_id="kg-001",
            tenant_id="tenant-001",
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
            credentials_path=None,
            schedule=Schedule(schedule_type=ScheduleType.MANUAL),
            last_sync_at=None,
            created_at=now,
            updated_at=now,
        )
        mock_ds_repo.get_by_id.return_value = ds

        await handler.handle(
            "MutationsApplied",
            _payload(
                sync_run_id=run.id,
                knowledge_graph_id="kg-001",
            ),
        )

        # DataSource should have been saved with updated last_sync_at
        mock_ds_repo.save.assert_called_once()
        saved_ds = mock_ds_repo.save.call_args[0][0]
        assert saved_ds.last_sync_at is not None


@pytest.mark.asyncio
class TestMutationApplicationFailedTransition:
    """MutationApplicationFailed → status = failed."""

    async def test_mutation_application_failed_sets_failed(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """MutationApplicationFailed should transition to 'failed'."""
        run = _make_sync_run(status="applying")
        mock_sync_run_repo.get_by_id.return_value = run

        await handler.handle(
            "MutationApplicationFailed",
            _payload(sync_run_id=run.id, error="DB write error"),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.status == "failed"
        assert saved_run.error == "DB write error"


@pytest.mark.asyncio
class TestTerminalStates:
    """Tests that terminal states (completed, failed) cannot be transitioned further.

    Spec: GIVEN a sync run in completed or failed status, THEN no further
    state transitions occur for that run.
    """

    async def test_completed_run_ignores_further_transitions(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """A completed sync run should not be transitioned to another state."""
        run = _make_sync_run(status="completed")
        mock_sync_run_repo.get_by_id.return_value = run

        # Try to transition a completed run
        await handler.handle("SyncStarted", _payload(sync_run_id=run.id))

        # save should NOT be called since run is already terminal
        mock_sync_run_repo.save.assert_not_called()

    async def test_failed_run_ignores_further_transitions(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """A failed sync run should not be transitioned to another state."""
        run = _make_sync_run(status="failed")
        mock_sync_run_repo.get_by_id.return_value = run

        # Try to transition a failed run
        await handler.handle("JobPackageProduced", _payload(sync_run_id=run.id))

        mock_sync_run_repo.save.assert_not_called()

    async def test_missing_sync_run_is_ignored_gracefully(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """Handler should not raise when sync run is not found (idempotency)."""
        mock_sync_run_repo.get_by_id.return_value = None

        # Should not raise
        await handler.handle("SyncStarted", _payload(sync_run_id="nonexistent"))

        mock_sync_run_repo.save.assert_not_called()
