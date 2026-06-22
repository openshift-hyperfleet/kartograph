"""Unit tests for MaintenancePipelineService."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrastructure.management.maintenance_pipeline_service import (
    MaintenancePipelineService,
)
from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.entities.data_source_sync_run import DataSourceSyncRun
from management.domain.events.data_source import SyncStarted
from management.domain.value_objects import (
    DataSourceId,
    KnowledgeGraphMaintenanceRunOutcome,
    KnowledgeGraphMaintenanceRunRecord,
    KnowledgeGraphMaintenanceSchedule,
    Schedule,
    ScheduleType,
)
from shared_kernel.datasource_types import DataSourceAdapterType
from tests.fakes.authorization import InMemoryAuthorizationProvider
from tests.fakes.management import (
    InMemoryDataSourceRepository,
    InMemoryKnowledgeGraphRepository,
)


def _make_kg(*, tenant_id: str = "tenant-1") -> KnowledgeGraph:
    return KnowledgeGraph.create(
        tenant_id=tenant_id,
        workspace_id="ws-1",
        name="Test KG",
        description="",
    )


def _make_ds(
    *,
    ds_id: str,
    kg_id: str,
    tenant_id: str,
    baseline: str = "abc",
    head: str = "def",
) -> DataSource:
    now = datetime.now(UTC)
    ds = DataSource(
        id=DataSourceId(value=ds_id),
        knowledge_graph_id=kg_id,
        tenant_id=tenant_id,
        name=f"source-{ds_id}",
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"repo_url": "https://example.com/repo.git"},
        credentials_path=None,
        schedule=Schedule(schedule_type=ScheduleType.MANUAL),
        last_sync_at=None,
        created_at=now,
        updated_at=now,
    )
    ds.last_extraction_baseline_commit = baseline
    ds.tracked_branch_head_commit = head
    ds.collect_events()
    return ds


async def _grant_kg_manage(
    authz: InMemoryAuthorizationProvider, kg_id: str, user_id: str
) -> None:
    await authz.write_relationship(
        f"knowledge_graph:{kg_id}", "admin", f"user:{user_id}"
    )


class _InMemorySyncRunRepository:
    def __init__(self) -> None:
        self.saved: dict[str, DataSourceSyncRun] = {}

    async def save(self, sync_run: DataSourceSyncRun) -> None:
        self.saved[sync_run.id] = sync_run

    async def get_by_id(self, sync_run_id: str) -> DataSourceSyncRun | None:
        return self.saved.get(sync_run_id)


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def session_factory(mock_session):
    @asynccontextmanager
    async def _cm():
        yield mock_session

    def factory():
        return _cm()

    return factory


@pytest.fixture
def kg_repo():
    return InMemoryKnowledgeGraphRepository()


@pytest.fixture
def ds_repo():
    return InMemoryDataSourceRepository()


@pytest.fixture
def sync_run_repo():
    return _InMemorySyncRunRepository()


@pytest.fixture
def authz():
    return InMemoryAuthorizationProvider()


def _service(
    *,
    mock_session,
    session_factory,
    kg_repo,
    ds_repo,
    sync_run_repo,
    authz,
    tenant_id: str = "tenant-1",
) -> MaintenancePipelineService:
    job_repo = MagicMock()
    job_repo.sync_maintenance_pending_jobs = AsyncMock()
    return MaintenancePipelineService(
        session=mock_session,
        session_factory=session_factory,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        sync_run_repository=sync_run_repo,
        extraction_job_repository=job_repo,
        authorization=authz,
        tenant_id=tenant_id,
        diff_summary_service_factory=lambda _tenant: MagicMock(),
    )


@pytest.mark.asyncio
async def test_trigger_records_no_changes_when_baselines_match(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(
        ds_id="ds-1",
        kg_id=kg.id.value,
        tenant_id=kg.tenant_id,
        baseline="same",
        head="same",
    )
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )

    run = await svc.trigger(user_id="user-1", kg_id=kg.id.value)

    assert run.outcome == KnowledgeGraphMaintenanceRunOutcome.NO_CHANGES
    assert sync_run_repo.saved == {}


@pytest.mark.asyncio
async def test_trigger_starts_ingest_only_for_changed_sources(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-changed", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )

    with patch.object(svc, "_wait_for_sync_runs", AsyncMock(return_value=["ingested"])):
        run = await svc.trigger(
            user_id="user-1",
            kg_id=kg.id.value,
            files_per_job=3,
            worker_count=4,
            start_extraction=False,
        )

    assert run.outcome == KnowledgeGraphMaintenanceRunOutcome.INGEST_STARTED
    assert run.files_per_job == 3
    assert run.worker_count == 4
    assert len(sync_run_repo.saved) == 1

    saved_ds = await ds_repo.get_by_id(ds.id)
    assert saved_ds is not None
    events = saved_ds.collect_events()
    assert len(events) == 1
    assert isinstance(events[0], SyncStarted)
    assert events[0].pipeline_mode == "ingest_only"


@pytest.mark.asyncio
async def test_trigger_rolls_back_session_when_ingest_launch_fails(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-changed", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )

    with patch.object(
        svc,
        "_launch_ingest_only_syncs",
        AsyncMock(side_effect=RuntimeError("launch failed")),
    ):
        run = await svc.trigger(
            user_id="user-1",
            kg_id=kg.id.value,
            start_extraction=False,
        )

    mock_session.rollback.assert_awaited_once()
    assert run.outcome == KnowledgeGraphMaintenanceRunOutcome.LAUNCH_FAILED
    assert "launch failed" in run.message


@pytest.mark.asyncio
async def test_trigger_skips_ingest_when_sources_already_prepared(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-prepared", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds.clone_head_commit = ds.tracked_branch_head_commit
    ds.last_prepared_commit = ds.tracked_branch_head_commit
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )
    expected = KnowledgeGraphMaintenanceRunRecord(
        run_id="run-materialized",
        triggered_at=datetime.now(UTC),
        outcome=KnowledgeGraphMaintenanceRunOutcome.EXTRACTION_STARTED,
        message="Materialized 3 maintenance job(s) and started extraction workers",
        jobs_materialized=3,
    )

    with patch.object(
        svc,
        "_materialize_and_start_extraction",
        AsyncMock(return_value=expected),
    ) as materialize:
        run = await svc.trigger(
            user_id="user-1",
            kg_id=kg.id.value,
            start_extraction=True,
        )

    assert run.outcome == KnowledgeGraphMaintenanceRunOutcome.EXTRACTION_STARTED
    assert sync_run_repo.saved == {}
    materialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_waits_for_ingest_before_materializing(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-changed", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )
    expected = KnowledgeGraphMaintenanceRunRecord(
        run_id="run-materialized",
        triggered_at=datetime.now(UTC),
        outcome=KnowledgeGraphMaintenanceRunOutcome.EXTRACTION_STARTED,
        message="Materialized 1 maintenance job(s) and started extraction workers",
        jobs_materialized=1,
    )

    with (
        patch.object(
            svc, "_wait_for_sync_runs", AsyncMock(return_value=["ingested"])
        ) as wait,
        patch.object(
            svc,
            "_materialize_and_start_extraction",
            AsyncMock(return_value=expected),
        ) as materialize,
    ):
        run = await svc.trigger(
            user_id="user-1",
            kg_id=kg.id.value,
            start_extraction=True,
        )

    assert run.outcome == KnowledgeGraphMaintenanceRunOutcome.EXTRACTION_STARTED
    wait.assert_awaited_once()
    materialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_persists_run_history_before_materializing(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-prepared", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds.clone_head_commit = ds.tracked_branch_head_commit
    ds.last_prepared_commit = ds.tracked_branch_head_commit
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )
    expected = KnowledgeGraphMaintenanceRunRecord(
        run_id="run-materialized",
        triggered_at=datetime.now(UTC),
        outcome=KnowledgeGraphMaintenanceRunOutcome.EXTRACTION_STARTED,
        message="Materialized 3 maintenance job(s) and started extraction workers",
        jobs_materialized=3,
    )

    with patch.object(
        svc,
        "_materialize_and_start_extraction",
        AsyncMock(return_value=expected),
    ) as materialize:
        run = await svc.trigger(
            user_id="user-1",
            kg_id=kg.id.value,
            start_extraction=True,
        )

    stored = await kg_repo.get_by_id(kg.id)
    assert stored is not None
    assert len(stored.maintenance_run_history) == 1
    assert stored.maintenance_run_history[-1].outcome in {
        KnowledgeGraphMaintenanceRunOutcome.STARTED,
        KnowledgeGraphMaintenanceRunOutcome.EXTRACTION_STARTED,
    }
    materialize.assert_awaited_once()
    assert run.outcome == KnowledgeGraphMaintenanceRunOutcome.EXTRACTION_STARTED


@pytest.mark.asyncio
async def test_materialize_commits_jobs_before_starting_orchestrator(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    now = datetime.now(UTC)
    kg.maintenance_run_history = (
        KnowledgeGraphMaintenanceRunRecord(
            run_id="run-1",
            triggered_at=now,
            outcome=KnowledgeGraphMaintenanceRunOutcome.STARTED,
            target_data_source_ids=("ds-prepared",),
            files_per_job=2,
            worker_count=4,
        ),
    )
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-prepared", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds.clone_head_commit = ds.tracked_branch_head_commit
    ds.last_prepared_commit = ds.tracked_branch_head_commit
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    job_repo = MagicMock()
    job_repo.sync_maintenance_pending_jobs = AsyncMock(return_value=2)
    svc = MaintenancePipelineService(
        session=mock_session,
        session_factory=session_factory,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        sync_run_repository=sync_run_repo,
        extraction_job_repository=job_repo,
        authorization=authz,
        tenant_id=kg.tenant_id,
        diff_summary_service_factory=lambda _tenant: MagicMock(),
    )

    call_order: list[str] = []

    async def track_commit() -> None:
        call_order.append("commit")

    job_repo.sync_maintenance_pending_jobs = AsyncMock(
        side_effect=lambda **_kwargs: call_order.append("sync") or 2,
    )
    mock_session.commit = AsyncMock(side_effect=track_commit)

    orchestrator = MagicMock()

    async def track_start(**_kwargs) -> None:
        call_order.append("start")

    orchestrator.start = AsyncMock(side_effect=track_start)

    with (
        patch(
            "infrastructure.management.maintenance_pipeline_service.collect_changed_maintenance_files",
            AsyncMock(return_value=[MagicMock()]),
        ),
        patch(
            "infrastructure.management.maintenance_pipeline_service.materialize_maintenance_jobs",
            return_value=[MagicMock()],
        ),
        patch(
            "infrastructure.management.maintenance_pipeline_service.get_extraction_run_orchestrator",
            return_value=orchestrator,
        ),
        patch(
            "infrastructure.management.maintenance_pipeline_service.SqlPreparedJobPackageReader",
        ) as reader_cls,
    ):
        reader_cls.return_value.list_latest_for_knowledge_graph = AsyncMock(
            return_value=()
        )
        await svc._materialize_and_start_extraction(
            kg_id=kg.id.value,
            tenant_id=kg.tenant_id,
        )

    assert call_order.index("sync") < call_order.index("commit")
    assert call_order.index("commit") < call_order.index("start")
    orchestrator.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_advance_marks_ingest_failed_when_sync_fails(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    now = datetime.now(UTC)
    sync_run_id = "sync-failed-1"
    await sync_run_repo.save(
        DataSourceSyncRun(
            id=sync_run_id,
            data_source_id="ds-changed",
            status="failed",
            started_at=now,
            completed_at=now,
            error="boom",
            created_at=now,
        )
    )
    kg.maintenance_run_history = (
        KnowledgeGraphMaintenanceRunRecord(
            run_id="run-1",
            triggered_at=now,
            outcome=KnowledgeGraphMaintenanceRunOutcome.INGEST_STARTED,
            target_data_source_ids=("ds-changed",),
            sync_run_ids=(sync_run_id,),
            files_per_job=2,
            worker_count=8,
        ),
    )
    kg_repo.seed(kg)

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )

    run = await svc.advance_for_knowledge_graph(
        kg_id=kg.id.value, tenant_id=kg.tenant_id
    )

    assert run is not None
    assert run.outcome == KnowledgeGraphMaintenanceRunOutcome.INGEST_FAILED


@pytest.mark.asyncio
async def test_check_scheduled_triggers_due_knowledge_graph(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    now = datetime.now(UTC)
    kg = _make_kg()
    kg.set_maintenance_schedule(
        KnowledgeGraphMaintenanceSchedule(
            enabled=True,
            cron_expression="0 2 * * *",
            timezone_name="UTC",
            next_run_at=now - timedelta(minutes=1),
            files_per_job=2,
            worker_count=8,
        )
    )
    kg_repo.seed(kg)

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )

    fake_repo = MagicMock()
    fake_repo.find_all = AsyncMock(return_value=[kg])
    fake_repo.save = AsyncMock()

    job_repo = MagicMock()
    job_repo.count_by_job_set = AsyncMock(return_value={"maintenance": {"failed": 0}})

    with (
        patch(
            "management.infrastructure.repositories.knowledge_graph_repository.KnowledgeGraphRepository",
            return_value=fake_repo,
        ),
        patch(
            "extraction.infrastructure.repositories.extraction_job_repository.ExtractionJobRepository",
            return_value=job_repo,
        ),
        patch.object(
            MaintenancePipelineService,
            "trigger_scheduled",
            AsyncMock(
                return_value=KnowledgeGraphMaintenanceRunRecord(
                    run_id="run-scheduled",
                    triggered_at=now,
                    outcome=KnowledgeGraphMaintenanceRunOutcome.NO_CHANGES,
                )
            ),
        ) as trigger_scheduled,
    ):
        triggered = await svc.check_scheduled_triggers(now=now)

    assert triggered == 1
    trigger_scheduled.assert_awaited_once()
    fake_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_scheduled_triggers_skips_when_failed_maintenance_jobs_remain(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    now = datetime.now(UTC)
    kg = _make_kg()
    kg.set_maintenance_schedule(
        KnowledgeGraphMaintenanceSchedule(
            enabled=True,
            cron_expression="0 2 * * *",
            timezone_name="UTC",
            next_run_at=now - timedelta(minutes=1),
            files_per_job=2,
            worker_count=8,
        )
    )
    kg_repo.seed(kg)

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
    )

    fake_repo = MagicMock()
    fake_repo.find_all = AsyncMock(return_value=[kg])
    fake_repo.save = AsyncMock()

    job_repo = MagicMock()
    job_repo.count_by_job_set = AsyncMock(
        return_value={"maintenance": {"failed": 2, "pending": 0, "in_progress": 0}}
    )

    with (
        patch(
            "management.infrastructure.repositories.knowledge_graph_repository.KnowledgeGraphRepository",
            return_value=fake_repo,
        ),
        patch(
            "extraction.infrastructure.repositories.extraction_job_repository.ExtractionJobRepository",
            return_value=job_repo,
        ),
        patch.object(
            MaintenancePipelineService,
            "trigger_scheduled",
            AsyncMock(),
        ) as trigger_scheduled,
    ):
        triggered = await svc.check_scheduled_triggers(now=now)

    assert triggered == 1
    trigger_scheduled.assert_not_awaited()
    fake_repo.save.assert_awaited_once()
    assert len(kg.maintenance_run_history) == 1
    assert (
        kg.maintenance_run_history[-1].outcome
        == KnowledgeGraphMaintenanceRunOutcome.PREFLIGHT_FAILED
    )
    assert (
        "failed maintenance job"
        in (kg.maintenance_run_history[-1].message or "").lower()
    )


@pytest.mark.asyncio
async def test_trigger_scheduled_refreshes_tracked_branch_heads(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(
        ds_id="ds-1",
        kg_id=kg.id.value,
        tenant_id=kg.tenant_id,
        baseline="abc",
        head="old-head",
    )
    ds_repo.seed(ds)

    ref_service = MagicMock()
    ref_service.resolve_tracked_head_commit = AsyncMock(return_value="new-head")
    svc = MaintenancePipelineService(
        session=mock_session,
        session_factory=session_factory,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        sync_run_repository=sync_run_repo,
        extraction_job_repository=MagicMock(),
        authorization=authz,
        tenant_id=kg.tenant_id,
        diff_summary_service_factory=lambda _tenant: MagicMock(),
        commit_reference_service_factory=lambda _tenant: ref_service,
    )

    with patch.object(
        svc,
        "_trigger_for_kg",
        AsyncMock(
            return_value=KnowledgeGraphMaintenanceRunRecord(
                run_id="run-scheduled",
                triggered_at=datetime.now(UTC),
                outcome=KnowledgeGraphMaintenanceRunOutcome.NO_CHANGES,
            )
        ),
    ) as trigger_for_kg:
        await svc.trigger_scheduled(
            kg_id=kg.id.value,
            files_per_job=2,
            worker_count=4,
        )

    ref_service.resolve_tracked_head_commit.assert_awaited_once()
    trigger_for_kg.assert_awaited_once()
    saved = await ds_repo.get_by_id(DataSourceId(value="ds-1"))
    assert saved is not None
    assert saved.tracked_branch_head_commit == "new-head"


@pytest.mark.asyncio
async def test_start_ready_maintenance_jobs_requires_queued_jobs(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    job_repo = MagicMock()
    job_repo.count_by_job_set = AsyncMock(return_value={})
    svc = MaintenancePipelineService(
        session=mock_session,
        session_factory=session_factory,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        sync_run_repository=sync_run_repo,
        extraction_job_repository=job_repo,
        authorization=authz,
        tenant_id=kg.tenant_id,
        diff_summary_service_factory=lambda _tenant: MagicMock(),
    )

    with pytest.raises(ValueError, match="No maintenance jobs are ready"):
        await svc.start_ready_maintenance_jobs(
            user_id="user-1",
            kg_id=kg.id.value,
            worker_count=4,
        )


@pytest.mark.asyncio
async def test_start_ready_maintenance_jobs_starts_workers_for_pending_jobs(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    job_repo = MagicMock()
    job_repo.count_by_job_set = AsyncMock(
        return_value={"maintenance": {"pending": 3, "in_progress": 0}}
    )
    svc = MaintenancePipelineService(
        session=mock_session,
        session_factory=session_factory,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        sync_run_repository=sync_run_repo,
        extraction_job_repository=job_repo,
        authorization=authz,
        tenant_id=kg.tenant_id,
        diff_summary_service_factory=lambda _tenant: MagicMock(),
    )
    orchestrator = MagicMock()
    orchestrator.start = AsyncMock()

    with patch(
        "infrastructure.management.maintenance_pipeline_service.get_extraction_run_orchestrator",
        return_value=orchestrator,
    ):
        result = await svc.start_ready_maintenance_jobs(
            user_id="user-1",
            kg_id=kg.id.value,
            worker_count=4,
        )

    orchestrator.start.assert_awaited_once_with(
        tenant_id=kg.tenant_id,
        knowledge_graph_id=kg.id.value,
        worker_count=4,
    )
    assert result["pending_jobs"] == 3
    assert "Started 4 worker(s)" in str(result["message"])
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_start_ready_maintenance_jobs_resumes_when_jobs_in_progress(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    job_repo = MagicMock()
    job_repo.count_by_job_set = AsyncMock(
        return_value={"maintenance": {"pending": 0, "in_progress": 2}}
    )
    svc = MaintenancePipelineService(
        session=mock_session,
        session_factory=session_factory,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        sync_run_repository=sync_run_repo,
        extraction_job_repository=job_repo,
        authorization=authz,
        tenant_id=kg.tenant_id,
        diff_summary_service_factory=lambda _tenant: MagicMock(),
    )
    orchestrator = MagicMock()
    orchestrator.start = AsyncMock()

    with patch(
        "infrastructure.management.maintenance_pipeline_service.get_extraction_run_orchestrator",
        return_value=orchestrator,
    ):
        result = await svc.start_ready_maintenance_jobs(
            user_id="user-1",
            kg_id=kg.id.value,
            worker_count=6,
        )

    orchestrator.start.assert_awaited_once()
    assert result["in_progress_jobs"] == 2
    assert "Resumed 6 worker(s)" in str(result["message"])


@pytest.mark.asyncio
async def test_regenerate_maintenance_jobs_replaces_pending_from_current_diff(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-1", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds.clone_head_commit = ds.tracked_branch_head_commit
    ds.last_prepared_commit = ds.tracked_branch_head_commit
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    job_repo = MagicMock()
    job_repo.sync_maintenance_pending_jobs = AsyncMock(return_value=3)
    svc = MaintenancePipelineService(
        session=mock_session,
        session_factory=session_factory,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        sync_run_repository=sync_run_repo,
        extraction_job_repository=job_repo,
        authorization=authz,
        tenant_id=kg.tenant_id,
        diff_summary_service_factory=lambda _tenant: MagicMock(),
    )

    with (
        patch.object(
            svc,
            "_build_maintenance_jobs",
            AsyncMock(
                return_value=([MagicMock(), MagicMock(), MagicMock()], [MagicMock()])
            ),
        ),
    ):
        result = await svc.regenerate_maintenance_jobs(
            user_id="user-1",
            kg_id=kg.id.value,
            files_per_job=2,
        )

    job_repo.sync_maintenance_pending_jobs.assert_awaited_once()
    mock_session.commit.assert_awaited()
    assert result["generated_jobs"] == 3
    assert "Regenerated 3 pending maintenance job(s)" in str(result["message"])


@pytest.mark.asyncio
async def test_regenerate_maintenance_jobs_requires_prepared_sources(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-1", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    svc = _service(
        mock_session=mock_session,
        session_factory=session_factory,
        kg_repo=kg_repo,
        ds_repo=ds_repo,
        sync_run_repo=sync_run_repo,
        authz=authz,
        tenant_id=kg.tenant_id,
    )

    with pytest.raises(ValueError, match="ingest prepare"):
        await svc.regenerate_maintenance_jobs(
            user_id="user-1",
            kg_id=kg.id.value,
            files_per_job=2,
        )


@pytest.mark.asyncio
async def test_regenerate_maintenance_jobs_blocks_while_jobs_running(
    mock_session, session_factory, kg_repo, ds_repo, sync_run_repo, authz
):
    kg = _make_kg()
    kg_repo.seed(kg)
    ds = _make_ds(ds_id="ds-1", kg_id=kg.id.value, tenant_id=kg.tenant_id)
    ds.clone_head_commit = ds.tracked_branch_head_commit
    ds.last_prepared_commit = ds.tracked_branch_head_commit
    ds_repo.seed(ds)
    await _grant_kg_manage(authz, kg.id.value, "user-1")

    job_repo = MagicMock()
    job_repo.sync_maintenance_pending_jobs = AsyncMock(
        side_effect=RuntimeError(
            "Cannot refresh maintenance jobs while 1 job(s) are running"
        )
    )
    svc = MaintenancePipelineService(
        session=mock_session,
        session_factory=session_factory,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        sync_run_repository=sync_run_repo,
        extraction_job_repository=job_repo,
        authorization=authz,
        tenant_id=kg.tenant_id,
        diff_summary_service_factory=lambda _tenant: MagicMock(),
    )

    with patch.object(
        svc,
        "_build_maintenance_jobs",
        AsyncMock(return_value=([MagicMock()], [MagicMock()])),
    ):
        with pytest.raises(RuntimeError, match="running"):
            await svc.regenerate_maintenance_jobs(
                user_id="user-1",
                kg_id=kg.id.value,
                files_per_job=2,
            )
