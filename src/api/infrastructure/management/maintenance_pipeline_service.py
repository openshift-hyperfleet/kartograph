"""Orchestrate knowledge-graph maintenance ingest and extraction jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from croniter import croniter
from ulid import ULID

from extraction.infrastructure.extraction_run_orchestrator import get_extraction_run_orchestrator
from extraction.infrastructure.prepared_job_package_reader import SqlPreparedJobPackageReader
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from extraction.infrastructure.workload_runtime_settings import (
    get_extraction_workload_runtime_settings,
)
from infrastructure.management.maintenance_changed_files import collect_changed_maintenance_files
from infrastructure.management.maintenance_job_materializer import (
    MAINTENANCE_JOB_SET_NAME,
    materialize_maintenance_jobs,
)
from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.entities.data_source_sync_run import DataSourceSyncRun
from management.domain.value_objects import (
    KnowledgeGraphId,
    KnowledgeGraphMaintenanceRunOutcome,
    KnowledgeGraphMaintenanceRunRecord,
    KnowledgeGraphMaintenanceSchedule,
)
from management.infrastructure.git_diff_summary_service import GitDiffSummaryService
from management.ports.exceptions import UnauthorizedError
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from management.ports.repositories import (
        IDataSourceRepository,
        IDataSourceSyncRunRepository,
        IKnowledgeGraphRepository,
    )


class MaintenancePipelineService:
    """Coordinate maintenance ingest, job materialization, and extraction workers."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
        knowledge_graph_repository: IKnowledgeGraphRepository,
        data_source_repository: IDataSourceRepository,
        sync_run_repository: IDataSourceSyncRunRepository,
        extraction_job_repository: ExtractionJobRepository,
        authorization: AuthorizationProvider,
        tenant_id: str,
        diff_summary_service_factory: Callable[[str], GitDiffSummaryService],
    ) -> None:
        self._session = session
        self._session_factory = session_factory
        self._kg_repo = knowledge_graph_repository
        self._ds_repo = data_source_repository
        self._sync_run_repo = sync_run_repository
        self._job_repo = extraction_job_repository
        self._authz = authorization
        self._tenant_id = tenant_id
        self._diff_summary_service_factory = diff_summary_service_factory

    async def trigger_scheduled(
        self,
        *,
        kg_id: str,
        files_per_job: int,
        worker_count: int,
    ) -> KnowledgeGraphMaintenanceRunRecord:
        """Start maintenance for a scheduled run without user authorization."""
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None:
            raise ValueError(f"Knowledge graph {kg_id} not found")
        return await self._trigger_for_kg(
            kg=kg,
            requested_by="maintenance-scheduler",
            files_per_job=files_per_job,
            worker_count=worker_count,
            start_extraction=True,
        )

    async def trigger(
        self,
        *,
        user_id: str,
        kg_id: str,
        files_per_job: int = 2,
        worker_count: int = 8,
        start_extraction: bool = True,
    ) -> KnowledgeGraphMaintenanceRunRecord:
        """Start maintenance ingest for changed sources on a knowledge graph."""
        kg = await self._require_manage_kg(user_id=user_id, kg_id=kg_id)
        return await self._trigger_for_kg(
            kg=kg,
            requested_by=user_id,
            files_per_job=files_per_job,
            worker_count=worker_count,
            start_extraction=start_extraction,
        )

    async def _trigger_for_kg(
        self,
        *,
        kg: KnowledgeGraph,
        requested_by: str,
        files_per_job: int,
        worker_count: int,
        start_extraction: bool,
    ) -> KnowledgeGraphMaintenanceRunRecord:
        kg_id = kg.id.value
        data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)
        run_id = str(ULID())
        now = datetime.now(UTC)
        normalized_files_per_job = max(1, int(files_per_job))
        normalized_workers = max(1, int(worker_count))

        if not data_sources:
            run = self._record_run(
                kg=kg,
                run=KnowledgeGraphMaintenanceRunRecord(
                    run_id=run_id,
                    triggered_at=now,
                    outcome=KnowledgeGraphMaintenanceRunOutcome.PREFLIGHT_FAILED,
                    message="No data sources connected to this knowledge graph",
                    files_per_job=normalized_files_per_job,
                    worker_count=normalized_workers,
                ),
            )
            await self._session.commit()
            return run

        changed_sources = self._changed_sources(data_sources)
        target_ids = tuple(ds.id.value for ds in data_sources)
        if not changed_sources:
            run = self._record_run(
                kg=kg,
                run=KnowledgeGraphMaintenanceRunRecord(
                    run_id=run_id,
                    triggered_at=now,
                    outcome=KnowledgeGraphMaintenanceRunOutcome.NO_CHANGES,
                    message="No source commit delta detected across connected data sources",
                    target_data_source_ids=target_ids,
                    files_per_job=normalized_files_per_job,
                    worker_count=normalized_workers,
                ),
            )
            await self._session.commit()
            return run

        try:
            sync_run_ids = await self._launch_ingest_only_syncs(
                changed_sources=changed_sources,
                requested_by=requested_by,
                now=now,
            )
            run = self._record_run(
                kg=kg,
                run=KnowledgeGraphMaintenanceRunRecord(
                    run_id=run_id,
                    triggered_at=now,
                    outcome=KnowledgeGraphMaintenanceRunOutcome.INGEST_STARTED,
                    message=(
                        "Maintenance ingest started for "
                        f"{len(changed_sources)} changed source(s)"
                    ),
                    target_data_source_ids=tuple(ds.id.value for ds in changed_sources),
                    sync_run_ids=sync_run_ids,
                    files_per_job=normalized_files_per_job,
                    worker_count=normalized_workers,
                ),
            )
            await self._session.commit()
            if start_extraction:
                advanced = await self.advance_for_knowledge_graph(
                    kg_id=kg_id,
                    tenant_id=kg.tenant_id,
                )
                if advanced is not None:
                    return advanced
            return run
        except Exception as exc:
            run = self._record_run(
                kg=kg,
                run=KnowledgeGraphMaintenanceRunRecord(
                    run_id=run_id,
                    triggered_at=now,
                    outcome=KnowledgeGraphMaintenanceRunOutcome.LAUNCH_FAILED,
                    message=f"Failed to launch maintenance ingest: {exc}",
                    target_data_source_ids=tuple(ds.id.value for ds in changed_sources),
                    files_per_job=normalized_files_per_job,
                    worker_count=normalized_workers,
                ),
            )
            await self._session.commit()
            return run

    async def advance_pending_pipelines(self) -> int:
        """Advance in-flight maintenance pipelines for all knowledge graphs."""
        advanced = 0
        async with self._session_factory() as session:
            from infrastructure.outbox.repository import OutboxRepository
            from management.infrastructure.repositories.knowledge_graph_repository import (
                KnowledgeGraphRepository,
            )

            outbox = OutboxRepository(session=session)
            kg_repo = KnowledgeGraphRepository(session=session, outbox=outbox)
            kgs = await kg_repo.find_all()
            for kg in kgs:
                if not kg.maintenance_run_history:
                    continue
                latest = kg.maintenance_run_history[-1]
                if latest.outcome != KnowledgeGraphMaintenanceRunOutcome.INGEST_STARTED:
                    continue
                service = self._with_session(session)
                result = await service.advance_for_knowledge_graph(
                    kg_id=kg.id.value,
                    tenant_id=kg.tenant_id,
                )
                if result is not None:
                    advanced += 1
            await session.commit()
        return advanced

    async def check_scheduled_triggers(self, *, now: datetime | None = None) -> int:
        """Trigger maintenance for knowledge graphs whose schedule is due."""
        current = now or datetime.now(UTC)
        triggered = 0
        async with self._session_factory() as session:
            from infrastructure.outbox.repository import OutboxRepository
            from management.infrastructure.repositories.knowledge_graph_repository import (
                KnowledgeGraphRepository,
            )

            outbox = OutboxRepository(session=session)
            kg_repo = KnowledgeGraphRepository(session=session, outbox=outbox)
            for kg in await kg_repo.find_all():
                schedule = kg.maintenance_schedule
                if schedule is None or not schedule.enabled:
                    continue
                if schedule.next_run_at is None or schedule.next_run_at > current:
                    continue
                service = self._with_session(session)
                await service.trigger_scheduled(
                    kg_id=kg.id.value,
                    files_per_job=schedule.files_per_job,
                    worker_count=schedule.worker_count,
                )
                kg.set_maintenance_schedule(
                    KnowledgeGraphMaintenanceSchedule(
                        enabled=schedule.enabled,
                        cron_expression=schedule.cron_expression,
                        timezone_name=schedule.timezone_name,
                        next_run_at=service._compute_next_run_at(
                            cron_expression=schedule.cron_expression,
                            timezone_name=schedule.timezone_name,
                            now=current,
                        ),
                        files_per_job=schedule.files_per_job,
                        worker_count=schedule.worker_count,
                    )
                )
                await kg_repo.save(kg)
                triggered += 1
            await session.commit()
        return triggered

    async def advance_for_knowledge_graph(
        self,
        *,
        kg_id: str,
        tenant_id: str,
    ) -> KnowledgeGraphMaintenanceRunRecord | None:
        """Materialize maintenance jobs and start workers when ingest has finished."""
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or not kg.maintenance_run_history:
            return None
        latest = kg.maintenance_run_history[-1]
        if latest.outcome != KnowledgeGraphMaintenanceRunOutcome.INGEST_STARTED:
            return None

        statuses = await self._sync_run_statuses(latest.sync_run_ids)
        if not statuses:
            return None
        if any(status in {"pending", "ingesting"} for status in statuses):
            return None
        if any(status == "failed" for status in statuses):
            run = self._replace_latest_run(
                kg=kg,
                latest=latest,
                outcome=KnowledgeGraphMaintenanceRunOutcome.INGEST_FAILED,
                message="One or more maintenance ingest syncs failed",
            )
            await self._kg_repo.save(kg)
            await self._session.commit()
            return run
        if not all(status == "ingested" for status in statuses):
            return None

        data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)
        changed_sources = [
            ds
            for ds in data_sources
            if ds.id.value in set(latest.target_data_source_ids)
        ]
        runtime_settings = get_extraction_workload_runtime_settings()
        prepared_reader = SqlPreparedJobPackageReader(
            session=self._session,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        )
        job_packages = await prepared_reader.list_latest_for_knowledge_graph(
            knowledge_graph_id=kg_id,
        )
        diff_service = self._diff_summary_service_factory(tenant_id)
        changed_files = await collect_changed_maintenance_files(
            diff_summary_service=diff_service,
            data_sources=changed_sources,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
            job_packages=job_packages,
        )
        files_per_job = latest.files_per_job or 2
        jobs = materialize_maintenance_jobs(
            knowledge_graph_id=kg_id,
            changed_files=changed_files,
            files_per_job=files_per_job,
        )
        if not jobs:
            run = self._replace_latest_run(
                kg=kg,
                latest=latest,
                outcome=KnowledgeGraphMaintenanceRunOutcome.NO_CHANGES,
                message="Ingest completed but no changed files were mapped to JobPackages",
                changed_file_count=0,
                jobs_materialized=0,
            )
            await self._kg_repo.save(kg)
            await self._session.commit()
            return run

        await self._job_repo.sync_maintenance_pending_jobs(
            knowledge_graph_id=kg_id,
            jobs=jobs,
            job_set_name=MAINTENANCE_JOB_SET_NAME,
        )
        orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
        await orchestrator.start(
            tenant_id=tenant_id,
            knowledge_graph_id=kg_id,
            worker_count=latest.worker_count or 8,
        )
        run = self._replace_latest_run(
            kg=kg,
            latest=latest,
            outcome=KnowledgeGraphMaintenanceRunOutcome.EXTRACTION_STARTED,
            message=(
                f"Materialized {len(jobs)} maintenance job(s) and started extraction workers"
            ),
            changed_file_count=len(changed_files),
            jobs_materialized=len(jobs),
        )
        await self._kg_repo.save(kg)
        await self._session.commit()
        return run

    def _with_session(self, session: AsyncSession) -> MaintenancePipelineService:
        from extraction.infrastructure.repositories.extraction_job_repository import (
            ExtractionJobRepository,
        )
        from infrastructure.outbox.repository import OutboxRepository
        from management.infrastructure.repositories.data_source_repository import (
            DataSourceRepository,
        )
        from management.infrastructure.repositories.data_source_sync_run_repository import (
            DataSourceSyncRunRepository,
        )
        from management.infrastructure.repositories.knowledge_graph_repository import (
            KnowledgeGraphRepository,
        )

        outbox = OutboxRepository(session=session)
        return MaintenancePipelineService(
            session=session,
            session_factory=self._session_factory,
            knowledge_graph_repository=KnowledgeGraphRepository(session=session, outbox=outbox),
            data_source_repository=DataSourceRepository(session=session, outbox=outbox),
            sync_run_repository=DataSourceSyncRunRepository(session=session),
            extraction_job_repository=ExtractionJobRepository(session=session),
            authorization=self._authz,
            tenant_id=self._tenant_id,
            diff_summary_service_factory=self._diff_summary_service_factory,
        )

    async def _require_manage_kg(self, *, user_id: str, kg_id: str) -> KnowledgeGraph:
        resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        subject = format_subject(ResourceType.USER, user_id)
        granted = await self._authz.check_permission(
            resource=resource,
            permission=Permission.MANAGE,
            subject=subject,
        )
        if not granted:
            raise UnauthorizedError(
                f"User {user_id} lacks manage permission on knowledge graph {kg_id}"
            )
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or kg.tenant_id != self._tenant_id:
            from management.ports.exceptions import KnowledgeGraphNotFoundError

            raise KnowledgeGraphNotFoundError(f"Knowledge graph {kg_id} not found")
        return kg

    @staticmethod
    def _changed_sources(data_sources: list[DataSource]) -> list[DataSource]:
        return [
            ds
            for ds in data_sources
            if ds.tracked_branch_head_commit is not None
            and ds.last_extraction_baseline_commit is not None
            and ds.tracked_branch_head_commit != ds.last_extraction_baseline_commit
        ]

    async def _launch_ingest_only_syncs(
        self,
        *,
        changed_sources: list[DataSource],
        requested_by: str,
        now: datetime,
    ) -> tuple[str, ...]:
        sync_run_ids: list[str] = []
        for data_source in changed_sources:
            sync_run_id = str(ULID())
            sync_run = DataSourceSyncRun(
                id=sync_run_id,
                data_source_id=data_source.id.value,
                status="pending",
                started_at=now,
                completed_at=None,
                error=None,
                created_at=now,
            )
            await self._sync_run_repo.save(sync_run)
            data_source.request_sync(
                sync_run_id=sync_run_id,
                requested_by=requested_by,
                pipeline_mode="ingest_only",
            )
            await self._ds_repo.save(data_source)
            sync_run_ids.append(sync_run_id)
        return tuple(sync_run_ids)

    async def _sync_run_statuses(self, sync_run_ids: tuple[str, ...]) -> list[str]:
        statuses: list[str] = []
        for sync_run_id in sync_run_ids:
            sync_run = await self._sync_run_repo.get_by_id(sync_run_id)
            if sync_run is None:
                continue
            statuses.append(sync_run.status)
        return statuses

    def _record_run(
        self,
        *,
        kg: KnowledgeGraph,
        run: KnowledgeGraphMaintenanceRunRecord,
    ) -> KnowledgeGraphMaintenanceRunRecord:
        kg.append_maintenance_run(run)
        return run

    def _replace_latest_run(
        self,
        *,
        kg: KnowledgeGraph,
        latest: KnowledgeGraphMaintenanceRunRecord,
        outcome: KnowledgeGraphMaintenanceRunOutcome,
        message: str,
        changed_file_count: int | None = None,
        jobs_materialized: int | None = None,
    ) -> KnowledgeGraphMaintenanceRunRecord:
        updated = KnowledgeGraphMaintenanceRunRecord(
            run_id=latest.run_id,
            triggered_at=latest.triggered_at,
            outcome=outcome,
            message=message,
            target_data_source_ids=latest.target_data_source_ids,
            sync_run_ids=latest.sync_run_ids,
            changed_file_count=(
                changed_file_count
                if changed_file_count is not None
                else latest.changed_file_count
            ),
            jobs_materialized=(
                jobs_materialized
                if jobs_materialized is not None
                else latest.jobs_materialized
            ),
            files_per_job=latest.files_per_job,
            worker_count=latest.worker_count,
        )
        history = list(kg.maintenance_run_history)
        history[-1] = updated
        kg.maintenance_run_history = tuple(history)
        return updated

    @staticmethod
    def _compute_next_run_at(
        *,
        cron_expression: str,
        timezone_name: str,
        now: datetime,
    ) -> datetime:
        from zoneinfo import ZoneInfo

        if not croniter.is_valid(cron_expression):
            raise ValueError(f"Invalid cron expression: {cron_expression!r}")
        tz = ZoneInfo(timezone_name)
        local_now = now.astimezone(tz)
        itr = croniter(cron_expression, local_now)
        next_local = itr.get_next(datetime)
        if next_local.tzinfo is None:
            next_local = next_local.replace(tzinfo=tz)
        return next_local.astimezone(UTC)
