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
from tests.fakes.management import InMemoryDataSourceRepository, InMemoryKnowledgeGraphRepository


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

    with patch.object(svc, "advance_for_knowledge_graph", AsyncMock(return_value=None)):
        run = await svc.trigger(
            user_id="user-1",
            kg_id=kg.id.value,
            files_per_job=3,
            worker_count=4,
            start_extraction=True,
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

    run = await svc.advance_for_knowledge_graph(kg_id=kg.id.value, tenant_id=kg.tenant_id)

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

    with (
        patch(
            "management.infrastructure.repositories.knowledge_graph_repository.KnowledgeGraphRepository",
            return_value=fake_repo,
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
