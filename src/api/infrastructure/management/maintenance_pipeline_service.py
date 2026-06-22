"""Orchestrate knowledge-graph maintenance ingest and extraction jobs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from croniter import croniter
from ulid import ULID

from extraction.infrastructure.extraction_run_orchestrator import (
    get_extraction_run_orchestrator,
)
from extraction.infrastructure.prepared_job_package_reader import (
    SqlPreparedJobPackageReader,
)
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from extraction.infrastructure.workload_runtime_settings import (
    get_extraction_workload_runtime_settings,
)
from infrastructure.management.maintenance_changed_files import (
    collect_changed_maintenance_files,
)
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
from management.infrastructure.git_commit_reference_service import (
    GitCommitReferenceService,
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

_START_READY_NO_JOBS_MESSAGE = (
    "No maintenance jobs are ready to run. Queue maintenance jobs from changed "
    "sources first."
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from management.ports.repositories import (
        IDataSourceRepository,
        IDataSourceSyncRunRepository,
        IKnowledgeGraphRepository,
    )

_MAINTENANCE_INGEST_WAIT_TIMEOUT_SECONDS = 300.0
_MAINTENANCE_INGEST_POLL_INTERVAL_SECONDS = 1.0


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
        commit_reference_service_factory: (
            Callable[[str], GitCommitReferenceService] | None
        ) = None,
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
        self._commit_reference_service_factory = commit_reference_service_factory

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
        await self._refresh_tracked_branch_heads(kg_id=kg_id, tenant_id=kg.tenant_id)
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

    async def start_ready_maintenance_jobs(
        self,
        *,
        user_id: str,
        kg_id: str,
        worker_count: int = 8,
    ) -> dict[str, int | str | bool]:
        """Start or resume workers for already-queued pending maintenance jobs."""
        kg = await self._require_manage_kg(user_id=user_id, kg_id=kg_id)
        normalized_workers = max(1, int(worker_count))
        counts = await self._job_repo.count_by_job_set(knowledge_graph_id=kg_id)
        maintenance_counts = counts.get(MAINTENANCE_JOB_SET_NAME, {})
        pending_jobs = int(maintenance_counts.get("pending", 0))
        in_progress_jobs = int(maintenance_counts.get("in_progress", 0))

        if pending_jobs <= 0 and in_progress_jobs <= 0:
            raise ValueError(_START_READY_NO_JOBS_MESSAGE)

        orchestrator = get_extraction_run_orchestrator(
            session_factory=self._session_factory
        )
        await orchestrator.start(
            tenant_id=kg.tenant_id,
            knowledge_graph_id=kg_id,
            worker_count=normalized_workers,
        )
        await self._session.commit()

        if pending_jobs > 0:
            message = (
                f"Started {normalized_workers} worker(s) for "
                f"{pending_jobs} ready maintenance job(s)"
            )
        else:
            message = (
                f"Resumed {normalized_workers} worker(s) while "
                f"{in_progress_jobs} maintenance job(s) are in progress"
            )
        return {
            "success": True,
            "message": message,
            "pending_jobs": pending_jobs,
            "in_progress_jobs": in_progress_jobs,
            "worker_count": normalized_workers,
        }

    async def regenerate_maintenance_jobs(
        self,
        *,
        user_id: str,
        kg_id: str,
        files_per_job: int = 2,
    ) -> dict[str, int | str | bool]:
        """Replace pending maintenance jobs from the current baseline-to-head diff."""
        kg = await self._require_manage_kg(user_id=user_id, kg_id=kg_id)
        normalized_files_per_job = max(1, int(files_per_job))
        data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)
        changed_sources = self._changed_sources(data_sources)
        if not changed_sources:
            return {
                "success": True,
                "generated_jobs": 0,
                "message": "No source commit delta detected across connected data sources",
            }

        needs_ingest = [
            ds for ds in changed_sources if self._source_needs_maintenance_ingest(ds)
        ]
        if needs_ingest:
            raise ValueError(
                f"{len(needs_ingest)} changed source(s) still need ingest prepare. "
                "Queue maintenance jobs to refresh JobPackages first."
            )

        jobs, changed_files = await self._build_maintenance_jobs(
            kg_id=kg_id,
            tenant_id=kg.tenant_id,
            changed_sources=changed_sources,
            files_per_job=normalized_files_per_job,
        )
        if not jobs:
            return {
                "success": True,
                "generated_jobs": 0,
                "message": "No changed files were mapped to prepared JobPackages",
            }

        await self._job_repo.sync_maintenance_pending_jobs(
            knowledge_graph_id=kg_id,
            jobs=jobs,
            job_set_name=MAINTENANCE_JOB_SET_NAME,
        )
        await self._session.commit()
        return {
            "success": True,
            "generated_jobs": len(jobs),
            "message": (
                f"Regenerated {len(jobs)} pending maintenance job(s) from "
                f"{len(changed_files)} changed file(s)"
            ),
        }

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
            return await self._persist_recorded_run(
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

        changed_sources = self._changed_sources(data_sources)
        needs_ingest = [
            ds for ds in changed_sources if self._source_needs_maintenance_ingest(ds)
        ]
        target_ids = tuple(ds.id.value for ds in data_sources)
        if not changed_sources:
            return await self._persist_recorded_run(
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

        try:
            phase = "start maintenance pipeline"
            sync_run_ids: tuple[str, ...] = ()
            if needs_ingest:
                phase = "launch maintenance ingest"
                sync_run_ids = await self._launch_ingest_only_syncs(
                    changed_sources=needs_ingest,
                    requested_by=requested_by,
                    now=now,
                )
            if needs_ingest:
                message = (
                    "Maintenance ingest started for "
                    f"{len(needs_ingest)} changed source(s)"
                )
                outcome = KnowledgeGraphMaintenanceRunOutcome.INGEST_STARTED
            else:
                message = (
                    f"Materializing maintenance jobs for {len(changed_sources)} "
                    "prepared source(s)"
                )
                outcome = KnowledgeGraphMaintenanceRunOutcome.STARTED
            run = await self._persist_recorded_run(
                kg=kg,
                run=KnowledgeGraphMaintenanceRunRecord(
                    run_id=run_id,
                    triggered_at=now,
                    outcome=outcome,
                    message=message,
                    target_data_source_ids=tuple(ds.id.value for ds in changed_sources),
                    sync_run_ids=sync_run_ids,
                    files_per_job=normalized_files_per_job,
                    worker_count=normalized_workers,
                ),
            )
            if not start_extraction:
                return run
            if needs_ingest:
                try:
                    statuses = await self._wait_for_sync_runs(sync_run_ids)
                except TimeoutError:
                    return await self._fail_latest_run(
                        kg_id=kg_id,
                        outcome=KnowledgeGraphMaintenanceRunOutcome.LAUNCH_FAILED,
                        message=(
                            "Maintenance ingest did not complete within "
                            f"{int(_MAINTENANCE_INGEST_WAIT_TIMEOUT_SECONDS)} seconds"
                        ),
                    )
                if any(status == "failed" for status in statuses):
                    return await self._fail_latest_run(
                        kg_id=kg_id,
                        outcome=KnowledgeGraphMaintenanceRunOutcome.INGEST_FAILED,
                        message="One or more maintenance ingest syncs failed",
                    )
                if not all(status == "ingested" for status in statuses):
                    return await self._fail_latest_run(
                        kg_id=kg_id,
                        outcome=KnowledgeGraphMaintenanceRunOutcome.LAUNCH_FAILED,
                        message="Maintenance ingest finished in an unexpected state",
                    )
            phase = "collect changed files and materialize maintenance jobs"
            advanced = await self._materialize_and_start_extraction(
                kg_id=kg_id,
                tenant_id=kg.tenant_id,
            )
            if advanced is not None:
                return advanced
            return run
        except Exception as exc:
            await self._session.rollback()
            return await self._persist_recorded_run(
                kg=kg,
                run=KnowledgeGraphMaintenanceRunRecord(
                    run_id=run_id,
                    triggered_at=now,
                    outcome=KnowledgeGraphMaintenanceRunOutcome.LAUNCH_FAILED,
                    message=f"Failed to {phase}: {exc}",
                    target_data_source_ids=tuple(ds.id.value for ds in changed_sources),
                    files_per_job=normalized_files_per_job,
                    worker_count=normalized_workers,
                ),
            )

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
                from extraction.infrastructure.repositories.extraction_job_repository import (
                    ExtractionJobRepository,
                )

                job_repo = ExtractionJobRepository(session)
                maintenance_counts = (
                    await job_repo.count_by_job_set(knowledge_graph_id=kg.id.value)
                ).get(MAINTENANCE_JOB_SET_NAME, {})
                failed_jobs = int(maintenance_counts.get("failed", 0))
                if failed_jobs > 0:
                    service._record_run(
                        kg=kg,
                        run=KnowledgeGraphMaintenanceRunRecord(
                            run_id=str(ULID()),
                            triggered_at=current,
                            outcome=KnowledgeGraphMaintenanceRunOutcome.PREFLIGHT_FAILED,
                            message=(
                                f"Scheduled maintenance skipped: {failed_jobs} failed "
                                "maintenance job(s) must be reset or addressed manually "
                                "before another scheduled run can proceed"
                            ),
                            files_per_job=schedule.files_per_job,
                            worker_count=schedule.worker_count,
                        ),
                    )
                else:
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

        return await self._materialize_and_start_extraction(
            kg_id=kg_id,
            tenant_id=tenant_id,
        )

    async def _materialize_and_start_extraction(
        self,
        *,
        kg_id: str,
        tenant_id: str,
    ) -> KnowledgeGraphMaintenanceRunRecord | None:
        """Materialize pending maintenance jobs and start extraction workers."""
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or not kg.maintenance_run_history:
            return None
        latest = kg.maintenance_run_history[-1]
        if latest.outcome not in {
            KnowledgeGraphMaintenanceRunOutcome.INGEST_STARTED,
            KnowledgeGraphMaintenanceRunOutcome.STARTED,
        }:
            return None

        data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)
        changed_sources = [
            ds
            for ds in data_sources
            if ds.id.value in set(latest.target_data_source_ids)
        ]
        files_per_job = latest.files_per_job or 2
        jobs, changed_files = await self._build_maintenance_jobs(
            kg_id=kg_id,
            tenant_id=tenant_id,
            changed_sources=changed_sources,
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
        await self._session.commit()

        orchestrator = get_extraction_run_orchestrator(
            session_factory=self._session_factory
        )
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

    async def _fail_latest_run(
        self,
        *,
        kg_id: str,
        outcome: KnowledgeGraphMaintenanceRunOutcome,
        message: str,
    ) -> KnowledgeGraphMaintenanceRunRecord:
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or not kg.maintenance_run_history:
            raise ValueError(f"Knowledge graph {kg_id} has no maintenance run history")
        latest = kg.maintenance_run_history[-1]
        run = self._replace_latest_run(
            kg=kg,
            latest=latest,
            outcome=outcome,
            message=message,
        )
        await self._kg_repo.save(kg)
        await self._session.commit()
        return run

    async def _wait_for_sync_runs(
        self,
        sync_run_ids: tuple[str, ...],
        *,
        timeout_seconds: float = _MAINTENANCE_INGEST_WAIT_TIMEOUT_SECONDS,
        poll_interval_seconds: float = _MAINTENANCE_INGEST_POLL_INTERVAL_SECONDS,
    ) -> list[str]:
        """Poll sync runs until all reach a terminal state or timeout."""
        if not sync_run_ids:
            return []
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            self._session.expire_all()
            statuses = await self._sync_run_statuses(sync_run_ids)
            if len(statuses) != len(sync_run_ids):
                await asyncio.sleep(poll_interval_seconds)
                continue
            if any(status in {"pending", "ingesting"} for status in statuses):
                await asyncio.sleep(poll_interval_seconds)
                continue
            return statuses
        raise TimeoutError("Maintenance ingest sync runs did not finish in time")

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
            knowledge_graph_repository=KnowledgeGraphRepository(
                session=session, outbox=outbox
            ),
            data_source_repository=DataSourceRepository(session=session, outbox=outbox),
            sync_run_repository=DataSourceSyncRunRepository(session=session),
            extraction_job_repository=ExtractionJobRepository(session=session),
            authorization=self._authz,
            tenant_id=self._tenant_id,
            diff_summary_service_factory=self._diff_summary_service_factory,
            commit_reference_service_factory=self._commit_reference_service_factory,
        )

    async def _refresh_tracked_branch_heads(
        self,
        *,
        kg_id: str,
        tenant_id: str,
    ) -> int:
        """Refresh stored branch tips from GitHub before a scheduled maintenance run."""
        if self._commit_reference_service_factory is None:
            return 0
        ref_service = self._commit_reference_service_factory(tenant_id)
        data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)
        updated = 0
        for data_source in data_sources:
            tracked_head = await ref_service.resolve_tracked_head_commit(data_source)
            if tracked_head is None:
                continue
            if data_source.tracked_branch_head_commit == tracked_head:
                continue
            data_source.tracked_branch_head_commit = tracked_head
            await self._ds_repo.save(data_source)
            updated += 1
        return updated

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

    async def _build_maintenance_jobs(
        self,
        *,
        kg_id: str,
        tenant_id: str,
        changed_sources: list[DataSource],
        files_per_job: int,
    ) -> tuple[list, list]:
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
        jobs = materialize_maintenance_jobs(
            knowledge_graph_id=kg_id,
            changed_files=changed_files,
            files_per_job=max(1, int(files_per_job)),
        )
        return jobs, changed_files

    @staticmethod
    def _changed_sources(data_sources: list[DataSource]) -> list[DataSource]:
        return [
            ds
            for ds in data_sources
            if ds.tracked_branch_head_commit is not None
            and ds.last_extraction_baseline_commit is not None
            and ds.tracked_branch_head_commit != ds.last_extraction_baseline_commit
        ]

    @staticmethod
    def _source_needs_maintenance_ingest(data_source: DataSource) -> bool:
        """True when local JobPackages must be refreshed before maintenance jobs run."""
        from management.domain.commit_pull_state import (
            has_unpulled_commits,
            resolve_ingested_head_commit,
        )

        if resolve_ingested_head_commit(data_source) is None:
            return True
        return has_unpulled_commits(data_source)

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

    async def _persist_recorded_run(
        self,
        *,
        kg: KnowledgeGraph,
        run: KnowledgeGraphMaintenanceRunRecord,
    ) -> KnowledgeGraphMaintenanceRunRecord:
        """Append a maintenance run record and flush it to PostgreSQL."""
        self._record_run(kg=kg, run=run)
        await self._kg_repo.save(kg)
        await self._session.commit()
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
