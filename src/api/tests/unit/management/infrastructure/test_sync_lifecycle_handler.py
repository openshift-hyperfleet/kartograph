"""Unit tests for SyncLifecycleHandler.

Tests verify each lifecycle event transitions the sync run to the correct status,
and that terminal states (completed, failed) cannot be transitioned further.

Spec coverage:
- Scenario: State transitions
- Scenario: Terminal states
- Scenario: Status updates
"""

from __future__ import annotations

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
    """Mock AsyncSession with async commit."""
    session = MagicMock()
    session.commit = AsyncMock()
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
        """Handler should support all lifecycle events."""
        expected = {
            "SyncStarted",
            "JobPackageProduced",
            "IngestionPrepared",
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
class TestIngestionPreparedTransition:
    """IngestionPrepared → status = ingested (terminal, no last_sync_at)."""

    async def test_ingestion_prepared_sets_ingested(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
        mock_ds_repo: AsyncMock,
    ):
        run = _make_sync_run(status="ingesting")
        mock_sync_run_repo.get_by_id.return_value = run

        from management.domain.aggregates import DataSource
        from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
        from shared_kernel.datasource_types import DataSourceAdapterType

        now = datetime.now(UTC)
        ds = DataSource(
            id=DataSourceId(value=run.data_source_id),
            knowledge_graph_id="kg-001",
            tenant_id="tenant-001",
            name="Repo",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"owner": "org", "repo": "repo"},
            credentials_path=None,
            schedule=Schedule(schedule_type=ScheduleType.MANUAL),
            last_sync_at=None,
            created_at=now,
            updated_at=now,
        )
        mock_ds_repo.get_by_id.return_value = ds

        await handler.handle(
            "IngestionPrepared",
            _payload(
                sync_run_id=run.id,
                job_package_id="pkg-001",
                prepared_commit_sha="abc123",
                prepared_file_count=99,
            ),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.status == "ingested"
        assert saved_run.completed_at is not None
        assert ds.last_prepared_commit == "abc123"
        assert ds.clone_head_commit == "abc123"
        assert ds.last_prepared_file_count == 99
        assert ds.last_extraction_baseline_commit == "abc123"
        mock_ds_repo.save.assert_awaited_once()

    async def test_ingestion_prepared_does_not_overwrite_existing_baseline(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
        mock_ds_repo: AsyncMock,
    ):
        run = _make_sync_run(status="ingesting")
        mock_sync_run_repo.get_by_id.return_value = run

        from management.domain.aggregates import DataSource
        from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
        from shared_kernel.datasource_types import DataSourceAdapterType

        now = datetime.now(UTC)
        ds = DataSource(
            id=DataSourceId(value=run.data_source_id),
            knowledge_graph_id="kg-001",
            tenant_id="tenant-001",
            name="Repo",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"owner": "org", "repo": "repo"},
            credentials_path=None,
            schedule=Schedule(schedule_type=ScheduleType.MANUAL),
            last_sync_at=None,
            last_extraction_baseline_commit="existing-baseline",
            created_at=now,
            updated_at=now,
        )
        mock_ds_repo.get_by_id.return_value = ds

        await handler.handle(
            "IngestionPrepared",
            _payload(
                sync_run_id=run.id,
                job_package_id="pkg-001",
                prepared_commit_sha="abc123",
                prepared_file_count=99,
            ),
        )

        assert ds.last_prepared_commit == "abc123"
        assert ds.last_extraction_baseline_commit == "existing-baseline"

    async def test_ingestion_prepared_seeds_unset_baselines_for_sibling_sources(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
        mock_ds_repo: AsyncMock,
    ):
        run = _make_sync_run(status="ingesting", ds_id="ds-a")
        mock_sync_run_repo.get_by_id.return_value = run

        from management.domain.aggregates import DataSource
        from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
        from shared_kernel.datasource_types import DataSourceAdapterType

        now = datetime.now(UTC)
        prepared_ds = DataSource(
            id=DataSourceId(value="ds-a"),
            knowledge_graph_id="kg-001",
            tenant_id="tenant-001",
            name="Prepared",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"owner": "org", "repo": "prepared"},
            credentials_path=None,
            schedule=Schedule(schedule_type=ScheduleType.MANUAL),
            last_sync_at=None,
            created_at=now,
            updated_at=now,
        )
        sibling_ds = DataSource(
            id=DataSourceId(value="ds-b"),
            knowledge_graph_id="kg-001",
            tenant_id="tenant-001",
            name="Sibling",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"owner": "org", "repo": "sibling"},
            credentials_path=None,
            schedule=Schedule(schedule_type=ScheduleType.MANUAL),
            last_sync_at=None,
            last_prepared_commit="sibling-prepared",
            clone_head_commit="sibling-prepared",
            created_at=now,
            updated_at=now,
        )
        mock_ds_repo.get_by_id.return_value = prepared_ds
        mock_ds_repo.find_by_knowledge_graph.return_value = [prepared_ds, sibling_ds]

        await handler.handle(
            "IngestionPrepared",
            _payload(
                sync_run_id=run.id,
                job_package_id="pkg-001",
                prepared_commit_sha="prepared-a",
                prepared_file_count=12,
            ),
        )

        assert prepared_ds.last_extraction_baseline_commit == "prepared-a"
        assert sibling_ds.last_extraction_baseline_commit == "sibling-prepared"
        assert mock_ds_repo.save.await_count == 2


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

    async def test_mutation_log_produced_stores_run_metadata(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
    ):
        """MutationLogProduced should persist run-level mutation metadata."""
        run = _make_sync_run(status="ai_extracting")
        mock_sync_run_repo.get_by_id.return_value = run

        await handler.handle(
            "MutationLogProduced",
            _payload(
                sync_run_id=run.id,
                knowledge_graph_id="kg-001",
                mutation_log_id="log-001",
                session_id="sess-001",
                actor_id="user-001",
                token_usage_total=1234,
                cost_total_usd=1.25,
                operation_counts={"create_node": 2, "update_edge": 1},
            ),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.mutation_log_run is not None
        assert saved_run.mutation_log_run.mutation_log_id == "log-001"
        assert saved_run.mutation_log_run.knowledge_graph_id == "kg-001"
        assert saved_run.mutation_log_run.session_id == "sess-001"
        assert saved_run.mutation_log_run.actor_id == "user-001"
        assert saved_run.mutation_log_run.token_usage_total == 1234
        assert saved_run.mutation_log_run.cost_total_usd == 1.25
        assert saved_run.mutation_log_run.operation_counts["create_node"] == 2


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

    async def test_mutations_applied_finalizes_mutation_log_metadata(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
        mock_ds_repo: AsyncMock,
    ):
        """MutationsApplied should finalize mutation run metrics and completed_at."""
        from management.domain.aggregates import DataSource
        from management.domain.entities import MutationLogRunMetadata
        from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
        from shared_kernel.datasource_types import DataSourceAdapterType

        run = _make_sync_run(status="applying")
        run.mutation_log_run = MutationLogRunMetadata(
            mutation_log_id="log-001",
            knowledge_graph_id="kg-001",
            session_id="sess-001",
            actor_id="user-001",
            started_at=datetime.now(UTC),
        )
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
                token_usage_total=4321,
                cost_total_usd=2.5,
                operation_counts={"create_node": 9},
            ),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert saved_run.mutation_log_run is not None
        assert saved_run.mutation_log_run.completed_at is not None
        assert saved_run.mutation_log_run.token_usage_total == 4321
        assert saved_run.mutation_log_run.cost_total_usd == 2.5
        assert saved_run.mutation_log_run.operation_counts == {"create_node": 9}

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
            tracked_branch_head_commit="processed-head",
            last_extraction_baseline_commit="old-baseline",
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
        assert saved_ds.last_extraction_baseline_commit == "processed-head"

    async def test_mutations_applied_logs_no_changes_short_circuit(
        self,
        handler: SyncLifecycleHandler,
        mock_sync_run_repo: AsyncMock,
        mock_ds_repo: AsyncMock,
    ):
        """No-change short-circuit should leave an explicit audit log entry."""
        from management.domain.aggregates import DataSource
        from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
        from shared_kernel.datasource_types import DataSourceAdapterType

        run = _make_sync_run(status="ingesting")
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
                no_changes_detected=True,
            ),
        )

        saved_run: DataSourceSyncRun = mock_sync_run_repo.save.call_args[0][0]
        assert any("No source changes were detected" in line for line in saved_run.logs)


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
