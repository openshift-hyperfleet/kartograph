"""Application service for extraction job configuration and execution."""

from __future__ import annotations

from typing import Any

from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.management.extraction_job_materializer import (
    entity_instance_counts_from_graph,
    materialize_jobs_from_config,
    projected_job_count,
)
from extraction.infrastructure.extraction_run_orchestrator import get_extraction_run_orchestrator
from extraction.domain.extraction_job import ExtractionJobStatus, ExtractionRunStatus
from extraction.infrastructure.repositories.extraction_job_repository import ExtractionJobRepository
from graph.infrastructure.bulk_data_reader import fetch_bulk_graph_data
from infrastructure.database.connection_pool import ConnectionPool
from management.application.services.knowledge_graph_service import KnowledgeGraphService
from management.domain.extraction_job_config import (
    ExtractionJobConfigDocument,
    ExtractionJobSetDefinition,
)
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)


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
        entity_types = [
            {"name": name, "instance_count": count}
            for name, count in sorted(counts.items(), key=lambda item: item[0])
        ]
        return {
            **document.to_dict(),
            "entity_types": entity_types,
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
        errors = document.validation_errors(entity_instance_counts=counts)
        if errors:
            raise ValueError("; ".join(errors))

        await self._knowledge_graph_repository.save_extraction_job_config(kg_id, document)
        await self._session.commit()
        return document.to_dict()

    async def regenerate_jobs(
        self,
        *,
        user_id: str,
        kg_id: str,
    ) -> dict[str, Any]:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        if kg is None:
            raise ValueError(f"Knowledge graph '{kg_id}' not found")

        if await self._extraction_job_repository.has_in_progress_jobs(knowledge_graph_id=kg_id):
            raise ValueError("Cannot regenerate jobs while extraction jobs are in progress.")

        config = await self._knowledge_graph_repository.get_extraction_job_config(kg_id)
        document = config or ExtractionJobConfigDocument.empty()
        graph_data = await self._load_graph_data()
        jobs = materialize_jobs_from_config(
            knowledge_graph_id=kg_id,
            config=document,
            graph_data=graph_data,
        )
        generated = await self._extraction_job_repository.replace_pending_jobs(
            knowledge_graph_id=kg_id,
            jobs=jobs,
        )
        await self._session.commit()
        return {"success": True, "generated_jobs": generated}

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
        return {
            "exists": True,
            "jobsByStatus": {
                "pending": counts.get("pending", 0),
                "in_progress": counts.get("in_progress", 0),
                "completed": counts.get("completed", 0),
                "failed": counts.get("failed", 0),
            },
            "jobsBySet": jobs_by_set,
            "recentJobs": [
                {
                    "jobId": job.job_id,
                    "jobSet": job.job_set_name,
                    "status": job.status.value,
                    "workerId": job.worker_id,
                    "startedAt": job.started_at.isoformat() if job.started_at else None,
                    "completedAt": job.completed_at.isoformat() if job.completed_at else None,
                    "inputTokens": job.input_tokens,
                    "outputTokens": job.output_tokens,
                    "writeOps": job.entities_created + job.entities_modified + job.relationships_created,
                    "assistantPreview": job.description[:120] if job.description else None,
                }
                for job in recent_jobs
            ],
            "activeWorkers": active_workers,
            "avgCompletedJobSeconds": avg_completed,
            "entitiesByType": entity_counts,
            "entitiesTotal": sum(entity_counts.values()),
            **token_metrics,
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
        job_sets = []
        for raw in payload.get("job_sets", []):
            job_set = ExtractionJobSetDefinition.from_dict(raw)
            job_sets.append(
                {
                    **raw,
                    "projected_jobs": projected_job_count(job_set, entity_instance_counts=counts),
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
        orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
        await orchestrator.halt(knowledge_graph_id=kg_id)
        await self._session.commit()
        return {"success": True, "message": "Extraction halted and incomplete jobs marked failed."}

    async def reset_stale_jobs(self, *, user_id: str, kg_id: str) -> dict[str, Any]:
        _ = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        reset = await self._extraction_job_repository.reset_jobs_by_status(
            knowledge_graph_id=kg_id,
            from_status=ExtractionJobStatus.IN_PROGRESS,
        )
        await self._session.commit()
        return {"success": True, "reset_count": reset}

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
