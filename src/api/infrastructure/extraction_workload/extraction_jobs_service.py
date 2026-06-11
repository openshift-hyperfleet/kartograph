"""Workload-scoped extraction job configuration for Graph Management Assistant tools."""

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
from extraction.domain.extraction_job import ExtractionJobStatus
from extraction.infrastructure.prepared_job_package_reader import SqlPreparedJobPackageReader
from extraction.infrastructure.repositories.extraction_job_repository import ExtractionJobRepository
from extraction.infrastructure.workload_runtime_settings import get_extraction_workload_runtime_settings
from graph.infrastructure.bulk_data_reader import fetch_bulk_graph_data
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.outbox.repository import OutboxRepository
from management.domain.extraction_job_config import (
    ExtractionJobConfigDocument,
    ExtractionJobSetDefinition,
    ExtractionJobSetStrategy,
)
from management.domain.value_objects import KnowledgeGraphId
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)


class GraphWorkloadExtractionJobsService:
    """Persist extraction job sets using workload JWT tenant/KG scope (no end-user session)."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        connection_pool: ConnectionPool,
    ) -> None:
        self._session = session
        self._connection_pool = connection_pool
        outbox = OutboxRepository(session=session)
        self._knowledge_graph_repository = KnowledgeGraphRepository(session=session, outbox=outbox)
        self._extraction_job_repository = ExtractionJobRepository(session=session)

    async def _assert_knowledge_graph_in_tenant(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> None:
        kg = await self._knowledge_graph_repository.get_by_id(
            KnowledgeGraphId(value=knowledge_graph_id)
        )
        if kg is None or kg.tenant_id != tenant_id:
            raise ValueError(f"Knowledge graph '{knowledge_graph_id}' not found")

    async def _load_graph_data(self, *, tenant_id: str) -> dict[str, Any]:
        graph_name = f"tenant_{tenant_id}"
        return await run_in_threadpool(
            fetch_bulk_graph_data,
            self._connection_pool,
            graph_name,
        )

    async def get_document(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> dict[str, Any]:
        await self._assert_knowledge_graph_in_tenant(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        config = await self._knowledge_graph_repository.get_extraction_job_config(
            knowledge_graph_id
        )
        document = config or ExtractionJobConfigDocument.empty()
        graph_data = await self._load_graph_data(tenant_id=tenant_id)
        counts = entity_instance_counts_from_graph(
            knowledge_graph_id=knowledge_graph_id,
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

    async def save_document(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        await self._assert_knowledge_graph_in_tenant(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        if await self._extraction_job_repository.has_in_progress_jobs(
            knowledge_graph_id=knowledge_graph_id
        ):
            raise ValueError("Cannot save job sets while extraction jobs are in progress.")

        document = ExtractionJobConfigDocument(
            version=str(payload.get("version") or "1.0"),
            job_sets=tuple(
                ExtractionJobSetDefinition.from_dict(row)
                for row in (payload.get("job_sets") or [])
            ),
        )
        graph_data = await self._load_graph_data(tenant_id=tenant_id)
        counts = entity_instance_counts_from_graph(
            knowledge_graph_id=knowledge_graph_id,
            graph_data=graph_data,
        )
        errors = document.validation_errors(entity_instance_counts=counts)
        if errors:
            raise ValueError("; ".join(errors))

        await self._knowledge_graph_repository.save_extraction_job_config(
            knowledge_graph_id,
            document,
        )

        runtime_settings = get_extraction_workload_runtime_settings()
        prepared_reader = SqlPreparedJobPackageReader(
            session=self._session,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        )
        job_packages = await prepared_reader.list_latest_for_knowledge_graph(
            knowledge_graph_id=knowledge_graph_id,
        )
        jobs = materialize_jobs_from_config(
            knowledge_graph_id=knowledge_graph_id,
            config=document,
            graph_data=graph_data,
            job_packages=job_packages,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        )
        generated = await self._extraction_job_repository.replace_pending_jobs(
            knowledge_graph_id=knowledge_graph_id,
            jobs=jobs,
        )
        await self._session.commit()

        saved = await self.get_document(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        saved["generated_jobs"] = generated
        return saved

    async def get_plan_summary(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> dict[str, Any]:
        document_payload = await self.get_document(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        counts = {
            row["name"]: row["instance_count"] for row in document_payload.get("entity_types", [])
        }
        runtime_settings = get_extraction_workload_runtime_settings()
        prepared_reader = SqlPreparedJobPackageReader(
            session=self._session,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        )
        job_packages = await prepared_reader.list_latest_for_knowledge_graph(
            knowledge_graph_id=knowledge_graph_id,
        )
        file_catalog = build_repository_file_catalog(
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
            job_packages=job_packages,
        )
        job_sets = []
        for raw in document_payload.get("job_sets", []):
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
        return {"job_sets": job_sets, "entity_types": document_payload.get("entity_types", [])}

    async def get_database_status(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> dict[str, Any]:
        await self._assert_knowledge_graph_in_tenant(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        counts = await self._extraction_job_repository.count_by_status(
            knowledge_graph_id=knowledge_graph_id
        )
        jobs_by_set = await self._extraction_job_repository.count_by_job_set(
            knowledge_graph_id=knowledge_graph_id
        )
        recent_jobs = await self._extraction_job_repository.list_recent_jobs(
            knowledge_graph_id=knowledge_graph_id,
            limit=20,
        )
        active_workers = await self._extraction_job_repository.list_active_workers(
            knowledge_graph_id=knowledge_graph_id
        )
        token_metrics = await self._extraction_job_repository.aggregate_token_metrics(
            knowledge_graph_id=knowledge_graph_id
        )
        avg_completed = await self._extraction_job_repository.avg_completed_job_seconds(
            knowledge_graph_id=knowledge_graph_id
        )
        graph_data = await self._load_graph_data(tenant_id=tenant_id)
        entity_counts = entity_instance_counts_from_graph(
            knowledge_graph_id=knowledge_graph_id,
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
                    "writeOps": job.entities_created
                    + job.entities_modified
                    + job.relationships_created,
                    "assistantPreview": job.description[:120] if job.description else None,
                }
                for job in recent_jobs
            ],
            "activeWorkers": active_workers,
            "avgCompletedJobSeconds": avg_completed,
            "entitiesByType": entity_counts,
            "entitiesTotal": sum(entity_counts.values()),
            **token_metrics,
            "hasInProgressJobs": counts.get(ExtractionJobStatus.IN_PROGRESS.value, 0) > 0,
        }
