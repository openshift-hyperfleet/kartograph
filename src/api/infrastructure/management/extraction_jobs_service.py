"""Application service for extraction job configuration and execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.management.extraction_job_materializer import (
    build_repository_file_catalog,
    entity_instance_counts_from_graph,
    match_file_patterns,
    materialize_jobs_from_config,
    projected_job_count,
)
from extraction.infrastructure.extraction_job_container import (
    stop_extraction_job_container,
    stop_extraction_job_containers,
)
from extraction.infrastructure.extraction_run_orchestrator import get_extraction_run_orchestrator
from extraction.domain.extraction_job import ExtractionJobStatus, ExtractionRunStatus
from extraction.infrastructure.extraction_job_activity import (
    job_workdir,
    parse_activity_messages,
    read_activity_log,
    serialize_job_detail,
    serialize_recent_job,
)
from extraction.infrastructure.prepared_job_package_reader import SqlPreparedJobPackageReader
from extraction.infrastructure.repositories.extraction_job_repository import ExtractionJobRepository
from extraction.infrastructure.workload_runtime_settings import get_extraction_workload_runtime_settings
from graph.infrastructure.bulk_data_reader import fetch_bulk_graph_data
from infrastructure.database.connection_pool import ConnectionPool
from management.application.services.knowledge_graph_service import KnowledgeGraphService
from management.domain.extraction_job_config import (
    ExtractionJobConfigDocument,
    ExtractionJobSetDefinition,
    ExtractionJobSetStrategy,
)
from management.domain.extraction_relationship_authoring import (
    edge_type_dicts_from_ontology,
    entity_type_authoring_context,
    node_type_dicts_from_ontology,
    relationship_authoring_by_entity_type,
)
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)


def _format_pending_sync_message(
    *,
    generated_jobs: int,
    enabled_job_set_count: int,
    disabled_job_set_count: int,
    warnings: tuple[str, ...],
) -> str:
    parts = [
        f"Synced {generated_jobs} pending job(s) from {enabled_job_set_count} enabled job set(s)."
    ]
    if disabled_job_set_count:
        parts.append(f"{disabled_job_set_count} disabled job set(s) were excluded.")
    if warnings:
        parts.append(" ".join(warnings))
    return " ".join(parts)


class ExtractionJobsService:
    """Coordinate extraction job sets, materialization, and run orchestration."""

    def __init__(
        self,
        *,
        knowledge_graph_service: KnowledgeGraphService,
        knowledge_graph_repository: KnowledgeGraphRepository,
        extraction_job_repository: ExtractionJobRepository,
        connection_pool: ConnectionPool,
        tenant_id: str,
        session: AsyncSession,
        session_factory: Any,
    ) -> None:
        self._knowledge_graph_service = knowledge_graph_service
        self._knowledge_graph_repository = knowledge_graph_repository
        self._extraction_job_repository = extraction_job_repository
        self._connection_pool = connection_pool
        self._tenant_id = tenant_id
        self._session = session
        self._session_factory = session_factory

    async def _load_graph_data(self) -> dict[str, Any]:
        graph_name = f"tenant_{self._tenant_id}"
        return await run_in_threadpool(
            fetch_bulk_graph_data,
            self._connection_pool,
            graph_name,
        )

    async def get_extraction_jobs_document(
        self,
        *,
        user_id: str,
        kg_id: str,
    ) -> dict[str, Any] | None:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            return None

        config = await self._knowledge_graph_repository.get_extraction_job_config(kg_id)
        document = config or ExtractionJobConfigDocument.empty()
        graph_data = await self._load_graph_data()
        counts = entity_instance_counts_from_graph(
            knowledge_graph_id=kg_id,
            graph_data=graph_data,
        )
        ontology = await self._knowledge_graph_repository.get_ontology(kg_id)
        edge_types = edge_type_dicts_from_ontology(ontology)
        node_types = node_type_dicts_from_ontology(ontology)
        entity_types = [
            {"name": name, "instance_count": count}
            for name, count in sorted(counts.items(), key=lambda item: item[0])
        ]
        authoring_context = {
            entity_type: entity_type_authoring_context(
                entity_type,
                node_types=node_types,
                edge_types=edge_types,
                entity_instance_counts=counts,
            )
            for entity_type in counts
        }
        return {
            **document.to_dict(),
            "entity_types": entity_types,
            "relationship_authoring_by_entity_type": relationship_authoring_by_entity_type(
                entity_instance_counts=counts,
                edge_types=edge_types,
            ),
            "entity_type_authoring_context": authoring_context,
        }

    async def save_extraction_jobs_document(
        self,
        *,
        user_id: str,
        kg_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            raise ValueError(f"Knowledge graph '{kg_id}' not found")

        document = ExtractionJobConfigDocument(
            version=str(payload.get("version") or "1.0"),
            job_sets=tuple(
                ExtractionJobSetDefinition.from_dict(row)
                for row in (payload.get("job_sets") or [])
            ),
        )
        graph_data = await self._load_graph_data()
        counts = entity_instance_counts_from_graph(
            knowledge_graph_id=kg_id,
            graph_data=graph_data,
        )
        ontology = await self._knowledge_graph_repository.get_ontology(kg_id)
        edge_types = edge_type_dicts_from_ontology(ontology)
        node_types = node_type_dicts_from_ontology(ontology)
        errors = document.validation_errors(
            entity_instance_counts=counts,
            edge_types=edge_types,
            node_types=node_types,
        )
        if errors:
            raise ValueError("; ".join(errors))

        await self._knowledge_graph_repository.save_extraction_job_config(kg_id, document)
        await self._session.commit()
        return document.to_dict()

    async def _materialize_and_sync_pending_jobs(
        self,
        *,
        kg_id: str,
        document: ExtractionJobConfigDocument,
    ) -> dict[str, Any]:
        graph_data = await self._load_graph_data()
        runtime_settings = get_extraction_workload_runtime_settings()
        prepared_reader = SqlPreparedJobPackageReader(
            session=self._session,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        )
        job_packages = await prepared_reader.list_latest_for_knowledge_graph(
            knowledge_graph_id=kg_id,
        )
        jobs = materialize_jobs_from_config(
            knowledge_graph_id=kg_id,
            config=document,
            graph_data=graph_data,
            job_packages=job_packages,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        )
        configured_names = {job_set.name for job_set in document.job_sets}
        enabled_names = {job_set.name for job_set in document.enabled_job_sets()}
        blocked_names = await self._extraction_job_repository.job_set_names_with_in_progress(
            knowledge_graph_id=kg_id,
        )
        generated, warnings = await self._extraction_job_repository.sync_pending_jobs(
            knowledge_graph_id=kg_id,
            jobs=jobs,
            configured_job_set_names=configured_names,
            enabled_job_set_names=enabled_names,
            blocked_job_set_names=blocked_names,
        )
        orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
        await orchestrator.ensure_workers_for_pending(
            tenant_id=self._tenant_id,
            knowledge_graph_id=kg_id,
        )
        disabled_count = len(configured_names - enabled_names)
        message = _format_pending_sync_message(
            generated_jobs=generated,
            enabled_job_set_count=len(enabled_names),
            disabled_job_set_count=disabled_count,
            warnings=warnings,
        )
        return {
            "success": True,
            "generated_jobs": generated,
            "warnings": list(warnings),
            "message": message,
        }

    async def regenerate_jobs(
        self,
        *,
        user_id: str,
        kg_id: str,
    ) -> dict[str, Any]:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            raise ValueError(f"Knowledge graph '{kg_id}' not found")

        config = await self._knowledge_graph_repository.get_extraction_job_config(kg_id)
        document = config or ExtractionJobConfigDocument.empty()
        result = await self._materialize_and_sync_pending_jobs(
            kg_id=kg_id,
            document=document,
        )
        await self._session.commit()
        return result

    async def _stop_in_progress_containers(self, *, kg_id: str) -> int:
        runtime_settings = get_extraction_workload_runtime_settings()
        job_ids = await self._extraction_job_repository.list_in_progress_job_ids(
            knowledge_graph_id=kg_id,
        )
        if not job_ids:
            return 0
        return stop_extraction_job_containers(
            job_ids=job_ids,
            container_engine=runtime_settings.container_engine,
        )

    async def cancel_job(
        self,
        *,
        user_id: str,
        kg_id: str,
        job_id: str,
    ) -> dict[str, Any]:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            raise ValueError(f"Knowledge graph '{kg_id}' not found")

        job = await self._extraction_job_repository.get_by_job_id(
            knowledge_graph_id=kg_id,
            job_id=job_id,
        )
        if job is None:
            raise ValueError(f"Extraction job '{job_id}' not found")

        runtime_settings = get_extraction_workload_runtime_settings()
        if job.status == ExtractionJobStatus.PENDING:
            removed = await self._extraction_job_repository.delete_pending_job(
                knowledge_graph_id=kg_id,
                job_id=job_id,
            )
            if not removed:
                raise ValueError(f"Job '{job_id}' is no longer pending.")
            await self._session.commit()
            return {
                "success": True,
                "message": f"Removed pending job {job_id} from the queue.",
            }

        if job.status != ExtractionJobStatus.IN_PROGRESS:
            raise ValueError(
                f"Job '{job_id}' is {job.status.value} and cannot be cancelled. "
                "Use Reset Failed or Reset All Jobs to re-queue finished jobs."
            )

        stop_extraction_job_container(
            job_id=job_id,
            container_engine=runtime_settings.container_engine,
        )
        await self._extraction_job_repository.mark_job_failed(
            knowledge_graph_id=kg_id,
            job_id=job_id,
            error_message="Cancelled by operator",
        )
        await self._session.commit()
        return {
            "success": True,
            "message": f"Cancelled running job {job_id} and stopped its container.",
        }

    async def get_database_status(
        self,
        *,
        user_id: str,
        kg_id: str,
    ) -> dict[str, Any] | None:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            return None

        counts = await self._extraction_job_repository.count_by_status(knowledge_graph_id=kg_id)
        jobs_by_set = await self._extraction_job_repository.count_by_job_set(
            knowledge_graph_id=kg_id
        )
        recent_jobs = await self._extraction_job_repository.list_recent_jobs(
            knowledge_graph_id=kg_id,
            limit=20,
        )
        active_workers = await self._extraction_job_repository.list_active_workers(
            knowledge_graph_id=kg_id
        )
        token_metrics = await self._extraction_job_repository.aggregate_token_metrics(
            knowledge_graph_id=kg_id
        )
        avg_completed = await self._extraction_job_repository.avg_completed_job_seconds(
            knowledge_graph_id=kg_id
        )
        graph_data = await self._load_graph_data()
        entity_counts = entity_instance_counts_from_graph(
            knowledge_graph_id=kg_id,
            graph_data=graph_data,
        )
        runtime_settings = get_extraction_workload_runtime_settings()
        return {
            "exists": True,
            "jobsByStatus": {
                "pending": counts.get("pending", 0),
                "in_progress": counts.get("in_progress", 0),
                "completed": counts.get("completed", 0),
                "archived": counts.get("archived", 0),
                "failed": counts.get("failed", 0),
            },
            "jobsBySet": jobs_by_set,
            "recentJobs": [
                serialize_recent_job(job, settings=runtime_settings)
                for job in recent_jobs
            ],
            "activeWorkers": active_workers,
            "avgCompletedJobSeconds": avg_completed,
            "entitiesByType": entity_counts,
            "entitiesTotal": sum(entity_counts.values()),
            **token_metrics,
        }

    async def get_job_detail(
        self,
        *,
        user_id: str,
        kg_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            return None
        job = await self._extraction_job_repository.get_by_job_id(
            knowledge_graph_id=kg_id,
            job_id=job_id,
        )
        if job is None:
            return None
        runtime_settings = get_extraction_workload_runtime_settings()
        return serialize_job_detail(job, settings=runtime_settings)

    async def get_job_activity(
        self,
        *,
        user_id: str,
        kg_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            return None
        job = await self._extraction_job_repository.get_by_job_id(
            knowledge_graph_id=kg_id,
            job_id=job_id,
        )
        if job is None:
            return None
        runtime_settings = get_extraction_workload_runtime_settings()
        workdir = job_workdir(
            knowledge_graph_id=kg_id,
            job_id=job_id,
            settings=runtime_settings,
        )
        raw_log = read_activity_log(workdir)
        return {
            "jobId": job.job_id,
            "status": job.status.value,
            "log": raw_log,
            "messages": parse_activity_messages(raw_log),
            "detail": serialize_job_detail(job, settings=runtime_settings),
        }

    async def get_extraction_run_state(
        self,
        *,
        user_id: str,
        kg_id: str,
    ) -> dict[str, Any] | None:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            return None

        run = await self._extraction_job_repository.get_run(knowledge_graph_id=kg_id)
        orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
        live = orchestrator.is_live(knowledge_graph_id=kg_id)
        if run is None:
            return {
                "live": live,
                "status": ExtractionRunStatus.IDLE.value,
                "workerCount": 0,
                "pauseRequested": False,
            }
        return {
            "live": live or run.status in {ExtractionRunStatus.RUNNING, ExtractionRunStatus.PAUSING},
            "status": run.status.value,
            "workerCount": run.worker_count,
            "pauseRequested": run.pause_requested,
            "startedAt": run.started_at.isoformat() if run.started_at else None,
            "completedAt": run.completed_at.isoformat() if run.completed_at else None,
            "orchestratorPid": run.orchestrator_pid,
        }

    async def get_extraction_plan_summary(
        self,
        *,
        user_id: str,
        kg_id: str,
    ) -> dict[str, Any] | None:
        payload = await self.get_extraction_jobs_document(user_id=user_id, kg_id=kg_id)
        if payload is None:
            return None
        counts = {
            row["name"]: row["instance_count"] for row in payload.get("entity_types", [])
        }
        runtime_settings = get_extraction_workload_runtime_settings()
        prepared_reader = SqlPreparedJobPackageReader(
            session=self._session,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        )
        job_packages = await prepared_reader.list_latest_for_knowledge_graph(
            knowledge_graph_id=kg_id,
        )
        file_catalog = build_repository_file_catalog(
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
            job_packages=job_packages,
        )
        job_sets = []
        for raw in payload.get("job_sets", []):
            job_set = ExtractionJobSetDefinition.from_dict(raw)
            matched_file_count = None
            if job_set.strategy == ExtractionJobSetStrategy.BY_FILES:
                matched_file_count = len(match_file_patterns(file_catalog, job_set.file_patterns))
            job_sets.append(
                {
                    **raw,
                    "projected_jobs": projected_job_count(
                        job_set,
                        entity_instance_counts=counts,
                        matched_file_count=matched_file_count,
                    ),
                }
            )
        return {"job_sets": job_sets, "entity_types": payload.get("entity_types", [])}

    async def start_extraction(
        self,
        *,
        user_id: str,
        kg_id: str,
        workers: int,
    ) -> dict[str, Any]:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            raise ValueError(f"Knowledge graph '{kg_id}' not found")

        orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
        await orchestrator.start(
            tenant_id=self._tenant_id,
            knowledge_graph_id=kg_id,
            worker_count=max(1, workers),
        )
        await self._session.commit()
        return {
            "success": True,
            "message": f"Started extraction with {max(1, workers)} worker(s).",
        }

    async def pause_extraction(self, *, user_id: str, kg_id: str) -> dict[str, Any]:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            raise ValueError(f"Knowledge graph '{kg_id}' not found")
        orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
        await orchestrator.request_pause(knowledge_graph_id=kg_id)
        await self._session.commit()
        return {"success": True, "message": "Pause requested; in-flight jobs will finish first."}

    async def halt_extraction(self, *, user_id: str, kg_id: str) -> dict[str, Any]:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            raise ValueError(f"Knowledge graph '{kg_id}' not found")
        job_ids = await self._extraction_job_repository.list_in_progress_job_ids(
            knowledge_graph_id=kg_id,
        )
        orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
        await orchestrator.halt(knowledge_graph_id=kg_id)
        runtime_settings = get_extraction_workload_runtime_settings()
        stopped = stop_extraction_job_containers(
            job_ids=job_ids,
            container_engine=runtime_settings.container_engine,
        )
        await self._session.commit()
        return {
            "success": True,
            "message": (
                "Extraction halted, incomplete jobs marked failed, and "
                f"{stopped} extraction container(s) stopped."
            ),
        }

    async def reset_stale_jobs(self, *, user_id: str, kg_id: str) -> dict[str, Any]:
        _ = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
        await orchestrator.stop_workers(knowledge_graph_id=kg_id)
        stopped = await self._stop_in_progress_containers(kg_id=kg_id)
        reset = await self._extraction_job_repository.reset_jobs_by_status(
            knowledge_graph_id=kg_id,
            from_status=ExtractionJobStatus.IN_PROGRESS,
        )
        await self._session.commit()
        return {
            "success": True,
            "reset_count": reset,
            "containers_stopped": stopped,
            "message": (
                f"Reset {reset} running job(s) to pending and stopped {stopped} container(s)."
            ),
        }

    async def get_archived_extraction_history(
        self,
        *,
        user_id: str,
        kg_id: str,
    ) -> dict[str, Any] | None:
        from extraction.application.archived_extraction_history import (
            group_archived_jobs_by_run_and_set,
        )

        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            return None
        jobs = await self._extraction_job_repository.list_archived_jobs(
            knowledge_graph_id=kg_id,
        )
        runs = group_archived_jobs_by_run_and_set(jobs)
        return {
            "archivedJobCount": len(jobs),
            "runs": runs,
        }

    async def get_archived_job_mutations(
        self,
        *,
        user_id: str,
        kg_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            return None
        job = await self._extraction_job_repository.get_by_job_id(
            knowledge_graph_id=kg_id,
            job_id=job_id,
        )
        if job is None or job.status != ExtractionJobStatus.ARCHIVED:
            return None
        return {
            "jobId": job.job_id,
            "jobSet": job.job_set_name,
            "runStartedAt": job.run_started_at.isoformat() if job.run_started_at else None,
            "archivedAt": job.archived_at.isoformat() if job.archived_at else None,
            "jsonl": job.applied_mutations_jsonl or "",
            "writeOps": job.write_ops(),
        }

    async def reset_completed_jobs(self, *, user_id: str, kg_id: str) -> dict[str, Any]:
        _ = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        reset = await self._extraction_job_repository.reset_jobs_by_status(
            knowledge_graph_id=kg_id,
            from_status=ExtractionJobStatus.COMPLETED,
        )
        await self._session.commit()
        return {"success": True, "reset_count": reset}

    async def reset_failed_jobs(self, *, user_id: str, kg_id: str) -> dict[str, Any]:
        _ = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        reset = await self._extraction_job_repository.reset_jobs_by_status(
            knowledge_graph_id=kg_id,
            from_status=ExtractionJobStatus.FAILED,
        )
        await self._session.commit()
        return {"success": True, "reset_count": reset}

    async def reset_extraction(self, *, user_id: str, kg_id: str) -> dict[str, Any]:
        _ = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        reset = await self._extraction_job_repository.reset_all_non_pending(knowledge_graph_id=kg_id)
        await self._session.commit()
        return {"success": True, "reset_count": reset}
