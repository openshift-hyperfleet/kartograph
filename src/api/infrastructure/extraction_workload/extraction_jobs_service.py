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
from infrastructure.management.extraction_jobs_service import _format_pending_sync_message
from extraction.domain.extraction_job import ExtractionJobStatus
from extraction.infrastructure.extraction_job_activity import serialize_recent_job
from extraction.infrastructure.extraction_run_orchestrator import get_extraction_run_orchestrator
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
from management.domain.extraction_relationship_authoring import (
    edge_type_dicts_from_ontology,
    relationship_authoring_by_entity_type,
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
        session_factory: Any | None = None,
    ) -> None:
        self._session = session
        self._connection_pool = connection_pool
        self._session_factory = session_factory
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
        ontology = await self._knowledge_graph_repository.get_ontology(knowledge_graph_id)
        edge_types = edge_type_dicts_from_ontology(ontology)
        entity_types = [
            {"name": name, "instance_count": count}
            for name, count in sorted(counts.items(), key=lambda item: item[0])
        ]
        return {
            **document.to_dict(),
            "entity_types": entity_types,
            "relationship_authoring_by_entity_type": relationship_authoring_by_entity_type(
                entity_instance_counts=counts,
                edge_types=edge_types,
            ),
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
        ontology = await self._knowledge_graph_repository.get_ontology(knowledge_graph_id)
        edge_types = edge_type_dicts_from_ontology(ontology)
        errors = document.validation_errors(
            entity_instance_counts=counts,
            edge_types=edge_types,
        )
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
        configured_names = {job_set.name for job_set in document.job_sets}
        enabled_names = {job_set.name for job_set in document.enabled_job_sets()}
        blocked_names = await self._extraction_job_repository.job_set_names_with_in_progress(
            knowledge_graph_id=knowledge_graph_id,
        )
        generated, warnings = await self._extraction_job_repository.sync_pending_jobs(
            knowledge_graph_id=knowledge_graph_id,
            jobs=jobs,
            configured_job_set_names=configured_names,
            enabled_job_set_names=enabled_names,
            blocked_job_set_names=blocked_names,
        )
        if self._session_factory is not None:
            orchestrator = get_extraction_run_orchestrator(session_factory=self._session_factory)
            await orchestrator.ensure_workers_for_pending(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
            )
        await self._session.commit()

        saved = await self.get_document(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        saved["generated_jobs"] = generated
        saved["warnings"] = list(warnings)
        saved["message"] = _format_pending_sync_message(
            generated_jobs=generated,
            enabled_job_set_count=len(enabled_names),
            disabled_job_set_count=len(configured_names - enabled_names),
            warnings=warnings,
        )
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
        runtime_settings = get_extraction_workload_runtime_settings()
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
                serialize_recent_job(job, settings=runtime_settings)
                for job in recent_jobs
            ],
            "activeWorkers": active_workers,
            "avgCompletedJobSeconds": avg_completed,
            "entitiesByType": entity_counts,
            "entitiesTotal": sum(entity_counts.values()),
            **token_metrics,
            "hasInProgressJobs": counts.get(ExtractionJobStatus.IN_PROGRESS.value, 0) > 0,
        }
