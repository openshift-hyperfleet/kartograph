"""PostgreSQL repository for materialized extraction jobs and runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from extraction.domain.extraction_job import (
    ExtractionJobRecord,
    ExtractionJobStatus,
    ExtractionRunRecord,
    ExtractionRunStatus,
    ExtractionTargetFile,
    ExtractionTargetInstance,
)
from extraction.infrastructure.models.extraction_job import ExtractionJobModel, ExtractionRunModel


def _job_model_to_record(model: ExtractionJobModel) -> ExtractionJobRecord:
    return ExtractionJobRecord(
        id=model.id,
        knowledge_graph_id=model.knowledge_graph_id,
        job_id=model.job_id,
        job_set_name=model.job_set_name,
        strategy=model.strategy,
        status=ExtractionJobStatus(model.status),
        order_index=model.order_index,
        description=model.description,
        target_instances=tuple(
            ExtractionTargetInstance.from_dict(row) for row in (model.target_instances or [])
        ),
        target_files=tuple(
            ExtractionTargetFile.from_dict(row) for row in (model.target_files or [])
        ),
        worker_id=model.worker_id,
        started_at=model.started_at,
        completed_at=model.completed_at,
        error_message=model.error_message,
        attempt=model.attempt,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        cache_read_tokens=model.cache_read_tokens,
        cache_creation_tokens=model.cache_creation_tokens,
        cost_usd=model.cost_usd,
        entities_created=model.entities_created,
        entities_modified=model.entities_modified,
        relationships_created=model.relationships_created,
        relationships_modified=model.relationships_modified,
        run_started_at=model.run_started_at,
        archived_at=model.archived_at,
        applied_mutations_jsonl=model.applied_mutations_jsonl,
    )


def _run_model_to_record(model: ExtractionRunModel) -> ExtractionRunRecord:
    return ExtractionRunRecord(
        id=model.id,
        knowledge_graph_id=model.knowledge_graph_id,
        status=ExtractionRunStatus(model.status),
        worker_count=model.worker_count,
        started_at=model.started_at,
        completed_at=model.completed_at,
        pause_requested=model.pause_requested,
        orchestrator_pid=model.orchestrator_pid,
    )


class ExtractionJobRepository:
    """Persistence for extraction jobs and orchestrator runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_pending_jobs(
        self,
        *,
        knowledge_graph_id: str,
        jobs: list[ExtractionJobRecord],
    ) -> int:
        await self._session.execute(
            delete(ExtractionJobModel).where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.status == ExtractionJobStatus.PENDING.value,
            )
        )
        for job in jobs:
            self._session.add(
                ExtractionJobModel(
                    id=job.id,
                    knowledge_graph_id=job.knowledge_graph_id,
                    job_id=job.job_id,
                    job_set_name=job.job_set_name,
                    strategy=job.strategy,
                    status=job.status.value,
                    order_index=job.order_index,
                    description=job.description,
                    target_instances=[instance.to_dict() for instance in job.target_instances],
                    target_files=[target_file.to_dict() for target_file in job.target_files],
                )
            )
        await self._session.flush()
        return len(jobs)

    async def sync_pending_jobs(
        self,
        *,
        knowledge_graph_id: str,
        jobs: list[ExtractionJobRecord],
        configured_job_set_names: set[str],
        enabled_job_set_names: set[str],
        blocked_job_set_names: set[str],
    ) -> tuple[int, tuple[str, ...]]:
        """Replace pending jobs per enabled job set without touching active work."""
        warnings: list[str] = []
        for job_set_name in sorted(configured_job_set_names):
            if job_set_name not in enabled_job_set_names:
                await self._delete_pending_for_job_set(
                    knowledge_graph_id=knowledge_graph_id,
                    job_set_name=job_set_name,
                )
                continue
            if job_set_name in blocked_job_set_names:
                in_progress = await self.count_in_progress_for_job_set(
                    knowledge_graph_id=knowledge_graph_id,
                    job_set_name=job_set_name,
                )
                warnings.append(
                    f"Skipped refreshing pending jobs for '{job_set_name}' because "
                    f"{in_progress} job(s) are still running."
                )
                continue
            await self._delete_pending_for_job_set(
                knowledge_graph_id=knowledge_graph_id,
                job_set_name=job_set_name,
            )
            for job in jobs:
                if job.job_set_name != job_set_name:
                    continue
                self._session.add(
                    ExtractionJobModel(
                        id=job.id,
                        knowledge_graph_id=job.knowledge_graph_id,
                        job_id=job.job_id,
                        job_set_name=job.job_set_name,
                        strategy=job.strategy,
                        status=job.status.value,
                        order_index=job.order_index,
                        description=job.description,
                        target_instances=[
                            instance.to_dict() for instance in job.target_instances
                        ],
                        target_files=[
                            target_file.to_dict() for target_file in job.target_files
                        ],
                    )
                )

        stale_names = await self._list_pending_job_set_names(knowledge_graph_id=knowledge_graph_id)
        for job_set_name in stale_names:
            if job_set_name not in configured_job_set_names:
                await self._delete_pending_for_job_set(
                    knowledge_graph_id=knowledge_graph_id,
                    job_set_name=job_set_name,
                )

        await self._session.flush()
        generated = len(
            [
                job
                for job in jobs
                if job.job_set_name in enabled_job_set_names
                and job.job_set_name not in blocked_job_set_names
            ]
        )
        return generated, tuple(warnings)

    async def _delete_pending_for_job_set(
        self,
        *,
        knowledge_graph_id: str,
        job_set_name: str,
    ) -> None:
        await self._session.execute(
            delete(ExtractionJobModel).where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.job_set_name == job_set_name,
                ExtractionJobModel.status == ExtractionJobStatus.PENDING.value,
            )
        )

    async def _list_pending_job_set_names(self, *, knowledge_graph_id: str) -> set[str]:
        stmt = (
            select(ExtractionJobModel.job_set_name)
            .where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.status == ExtractionJobStatus.PENDING.value,
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return {str(row[0]) for row in result.all()}

    async def count_in_progress_for_job_set(
        self,
        *,
        knowledge_graph_id: str,
        job_set_name: str,
    ) -> int:
        stmt = select(func.count()).where(
            ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
            ExtractionJobModel.job_set_name == job_set_name,
            ExtractionJobModel.status == ExtractionJobStatus.IN_PROGRESS.value,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def job_set_names_with_in_progress(self, *, knowledge_graph_id: str) -> set[str]:
        stmt = (
            select(ExtractionJobModel.job_set_name)
            .where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.status == ExtractionJobStatus.IN_PROGRESS.value,
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return {str(row[0]) for row in result.all()}

    async def delete_pending_job(
        self,
        *,
        knowledge_graph_id: str,
        job_id: str,
    ) -> bool:
        result = await self._session.execute(
            delete(ExtractionJobModel).where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.job_id == job_id,
                ExtractionJobModel.status == ExtractionJobStatus.PENDING.value,
            )
        )
        return int(result.rowcount or 0) > 0

    async def list_in_progress_job_ids(self, *, knowledge_graph_id: str) -> list[str]:
        stmt = select(ExtractionJobModel.job_id).where(
            ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
            ExtractionJobModel.status == ExtractionJobStatus.IN_PROGRESS.value,
        )
        result = await self._session.execute(stmt)
        return [str(row[0]) for row in result.all()]

    async def count_by_status(self, *, knowledge_graph_id: str) -> dict[str, int]:
        stmt = (
            select(ExtractionJobModel.status, func.count())
            .where(ExtractionJobModel.knowledge_graph_id == knowledge_graph_id)
            .group_by(ExtractionJobModel.status)
        )
        result = await self._session.execute(stmt)
        counts = {status.value: 0 for status in ExtractionJobStatus}
        for status, count in result.all():
            counts[str(status)] = int(count)
        return counts

    async def count_by_job_set(self, *, knowledge_graph_id: str) -> dict[str, dict[str, int]]:
        stmt = (
            select(
                ExtractionJobModel.job_set_name,
                ExtractionJobModel.status,
                func.count(),
            )
            .where(ExtractionJobModel.knowledge_graph_id == knowledge_graph_id)
            .group_by(ExtractionJobModel.job_set_name, ExtractionJobModel.status)
        )
        result = await self._session.execute(stmt)
        grouped: dict[str, dict[str, int]] = {}
        for job_set_name, status, count in result.all():
            bucket = grouped.setdefault(
                job_set_name,
                {
                    "pending": 0,
                    "in_progress": 0,
                    "completed": 0,
                    "failed": 0,
                    "total": 0,
                },
            )
            bucket[str(status)] = int(count)
            bucket["total"] += int(count)
        return grouped

    async def has_in_progress_jobs(self, *, knowledge_graph_id: str) -> bool:
        stmt = select(func.count()).where(
            ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
            ExtractionJobModel.status == ExtractionJobStatus.IN_PROGRESS.value,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one()) > 0

    async def get_by_job_id(
        self,
        *,
        knowledge_graph_id: str,
        job_id: str,
    ) -> ExtractionJobRecord | None:
        stmt = select(ExtractionJobModel).where(
            ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
            ExtractionJobModel.job_id == job_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _job_model_to_record(model)

    async def list_recent_jobs(
        self,
        *,
        knowledge_graph_id: str,
        limit: int = 20,
    ) -> list[ExtractionJobRecord]:
        stmt = (
            select(ExtractionJobModel)
            .where(ExtractionJobModel.knowledge_graph_id == knowledge_graph_id)
            .order_by(
                ExtractionJobModel.updated_at.desc(),
                ExtractionJobModel.order_index.asc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_job_model_to_record(model) for model in result.scalars().all()]

    async def list_active_workers(self, *, knowledge_graph_id: str) -> list[dict[str, Any]]:
        stmt = select(ExtractionJobModel).where(
            ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
            ExtractionJobModel.status == ExtractionJobStatus.IN_PROGRESS.value,
        )
        result = await self._session.execute(stmt)
        workers: list[dict[str, Any]] = []
        for model in result.scalars().all():
            workers.append(
                {
                    "workerId": model.worker_id,
                    "jobId": model.job_id,
                    "jobSet": model.job_set_name,
                    "strategy": model.strategy,
                    "fileCount": len(model.target_files or []),
                    "instanceCount": len(model.target_instances or []),
                    "startedAt": model.started_at.isoformat() if model.started_at else None,
                }
            )
        return workers

    async def claim_next_pending_job(
        self,
        *,
        knowledge_graph_id: str,
        worker_id: str,
    ) -> ExtractionJobRecord | None:
        stmt = (
            select(ExtractionJobModel)
            .where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.status == ExtractionJobStatus.PENDING.value,
            )
            .order_by(ExtractionJobModel.order_index.asc(), ExtractionJobModel.job_id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        run = await self.get_run(knowledge_graph_id=knowledge_graph_id)
        model.status = ExtractionJobStatus.IN_PROGRESS.value
        model.worker_id = worker_id
        model.started_at = datetime.now(UTC)
        if run is not None and run.started_at is not None:
            model.run_started_at = run.started_at
        model.attempt = int(model.attempt) + 1
        await self._session.flush()
        return _job_model_to_record(model)

    async def mark_job_completed(
        self,
        *,
        knowledge_graph_id: str,
        job_id: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        payload = metrics or {}
        entities_created = int(payload.get("entities_created", 0))
        entities_modified = int(payload.get("entities_modified", 0))
        relationships_created = int(payload.get("relationships_created", 0))
        relationships_modified = int(payload.get("relationships_modified", 0))
        write_ops = int(
            payload.get("write_ops")
            or (
                entities_created
                + entities_modified
                + relationships_created
                + relationships_modified
            )
        )
        now = datetime.now(UTC)
        status = (
            ExtractionJobStatus.ARCHIVED.value
            if write_ops > 0
            else ExtractionJobStatus.COMPLETED.value
        )
        values: dict[str, Any] = {
            "status": status,
            "completed_at": now,
            "input_tokens": int(payload.get("input_tokens", 0)),
            "output_tokens": int(payload.get("output_tokens", 0)),
            "cache_read_tokens": int(payload.get("cache_read_tokens", 0)),
            "cache_creation_tokens": int(payload.get("cache_creation_tokens", 0)),
            "cost_usd": float(payload.get("cost_usd", 0.0)),
            "entities_created": entities_created,
            "entities_modified": entities_modified,
            "relationships_created": relationships_created,
            "relationships_modified": relationships_modified,
        }
        if write_ops > 0:
            values["archived_at"] = now
            applied_jsonl = payload.get("applied_mutations_jsonl")
            if isinstance(applied_jsonl, str) and applied_jsonl.strip():
                values["applied_mutations_jsonl"] = applied_jsonl
        await self._session.execute(
            update(ExtractionJobModel)
            .where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.job_id == job_id,
            )
            .values(**values)
        )

    async def mark_job_failed(
        self,
        *,
        knowledge_graph_id: str,
        job_id: str,
        error_message: str,
    ) -> None:
        await self._session.execute(
            update(ExtractionJobModel)
            .where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.job_id == job_id,
            )
            .values(
                status=ExtractionJobStatus.FAILED.value,
                completed_at=datetime.now(UTC),
                error_message=error_message,
            )
        )

    async def mark_in_progress_failed(
        self,
        *,
        knowledge_graph_id: str,
        error_message: str,
    ) -> int:
        result = await self._session.execute(
            update(ExtractionJobModel)
            .where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.status == ExtractionJobStatus.IN_PROGRESS.value,
            )
            .values(
                status=ExtractionJobStatus.FAILED.value,
                completed_at=datetime.now(UTC),
                error_message=error_message,
            )
        )
        return int(result.rowcount or 0)

    async def reset_jobs_by_status(
        self,
        *,
        knowledge_graph_id: str,
        from_status: ExtractionJobStatus,
        to_status: ExtractionJobStatus = ExtractionJobStatus.PENDING,
    ) -> int:
        result = await self._session.execute(
            update(ExtractionJobModel)
            .where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.status == from_status.value,
            )
            .values(
                status=to_status.value,
                worker_id=None,
                started_at=None,
                completed_at=None,
                error_message=None,
            )
        )
        return int(result.rowcount or 0)

    async def reset_all_non_pending(
        self,
        *,
        knowledge_graph_id: str,
    ) -> int:
        total = 0
        for status in (
            ExtractionJobStatus.IN_PROGRESS,
            ExtractionJobStatus.COMPLETED,
            ExtractionJobStatus.FAILED,
        ):
            total += await self.reset_jobs_by_status(
                knowledge_graph_id=knowledge_graph_id,
                from_status=status,
            )
        return total

    async def insert_archived_session_job(self, job: ExtractionJobRecord) -> None:
        """Persist one archived Graph Management Assistant session mutation log."""
        self._session.add(
            ExtractionJobModel(
                id=job.id,
                knowledge_graph_id=job.knowledge_graph_id,
                job_id=job.job_id,
                job_set_name=job.job_set_name,
                strategy=job.strategy,
                status=job.status.value,
                order_index=job.order_index,
                description=job.description,
                target_instances=[instance.to_dict() for instance in job.target_instances],
                target_files=[target_file.to_dict() for target_file in job.target_files],
                started_at=job.started_at,
                completed_at=job.completed_at,
                entities_created=job.entities_created,
                entities_modified=job.entities_modified,
                relationships_created=job.relationships_created,
                relationships_modified=job.relationships_modified,
                run_started_at=job.run_started_at,
                archived_at=job.archived_at,
                applied_mutations_jsonl=job.applied_mutations_jsonl,
                input_tokens=job.input_tokens,
                output_tokens=job.output_tokens,
                cache_read_tokens=job.cache_read_tokens,
                cache_creation_tokens=job.cache_creation_tokens,
                cost_usd=job.cost_usd,
            )
        )
        await self._session.flush()

    async def list_archived_jobs(
        self,
        *,
        knowledge_graph_id: str,
        limit: int = 500,
    ) -> list[ExtractionJobRecord]:
        stmt = (
            select(ExtractionJobModel)
            .where(
                ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionJobModel.status == ExtractionJobStatus.ARCHIVED.value,
            )
            .order_by(
                ExtractionJobModel.run_started_at.desc().nullslast(),
                ExtractionJobModel.archived_at.desc().nullslast(),
                ExtractionJobModel.job_set_name.asc(),
                ExtractionJobModel.order_index.asc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_job_model_to_record(model) for model in result.scalars().all()]

    async def aggregate_token_metrics(self, *, knowledge_graph_id: str) -> dict[str, float | int]:
        stmt = select(
            func.coalesce(func.sum(ExtractionJobModel.input_tokens), 0),
            func.coalesce(func.sum(ExtractionJobModel.output_tokens), 0),
            func.coalesce(func.sum(ExtractionJobModel.cache_read_tokens), 0),
            func.coalesce(func.sum(ExtractionJobModel.cache_creation_tokens), 0),
            func.coalesce(func.sum(ExtractionJobModel.cost_usd), 0.0),
        ).where(ExtractionJobModel.knowledge_graph_id == knowledge_graph_id)
        result = await self._session.execute(stmt)
        row = result.one()
        return {
            "totalInputTokens": int(row[0]),
            "totalOutputTokens": int(row[1]),
            "totalCacheReadTokens": int(row[2]),
            "totalCacheCreationTokens": int(row[3]),
            "totalCostUsd": float(row[4]),
        }

    async def avg_completed_job_seconds(self, *, knowledge_graph_id: str) -> float | None:
        stmt = select(
            func.avg(
                func.extract(
                    "epoch",
                    ExtractionJobModel.completed_at - ExtractionJobModel.started_at,
                )
            )
        ).where(
            ExtractionJobModel.knowledge_graph_id == knowledge_graph_id,
            ExtractionJobModel.status == ExtractionJobStatus.COMPLETED.value,
            ExtractionJobModel.started_at.is_not(None),
            ExtractionJobModel.completed_at.is_not(None),
        )
        result = await self._session.execute(stmt)
        value = result.scalar_one_or_none()
        if value is None:
            return None
        seconds = float(value)
        return seconds if seconds > 0 else None

    async def get_run(self, *, knowledge_graph_id: str) -> ExtractionRunRecord | None:
        stmt = select(ExtractionRunModel).where(
            ExtractionRunModel.knowledge_graph_id == knowledge_graph_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _run_model_to_record(model) if model else None

    async def upsert_run(
        self,
        *,
        knowledge_graph_id: str,
        status: ExtractionRunStatus,
        worker_count: int,
        pause_requested: bool = False,
        orchestrator_pid: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> ExtractionRunRecord:
        stmt = select(ExtractionRunModel).where(
            ExtractionRunModel.knowledge_graph_id == knowledge_graph_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = ExtractionRunModel(
                id=str(ULID()),
                knowledge_graph_id=knowledge_graph_id,
                status=status.value,
                worker_count=worker_count,
                pause_requested=pause_requested,
                orchestrator_pid=orchestrator_pid,
                started_at=started_at,
                completed_at=completed_at,
            )
            self._session.add(model)
        else:
            model.status = status.value
            model.worker_count = worker_count
            model.pause_requested = pause_requested
            model.orchestrator_pid = orchestrator_pid
            if started_at is not None:
                model.started_at = started_at
            if completed_at is not None:
                model.completed_at = completed_at
        await self._session.flush()
        return _run_model_to_record(model)

    async def set_pause_requested(self, *, knowledge_graph_id: str, pause_requested: bool) -> None:
        await self._session.execute(
            update(ExtractionRunModel)
            .where(ExtractionRunModel.knowledge_graph_id == knowledge_graph_id)
            .values(pause_requested=pause_requested)
        )

    async def is_pause_requested(self, *, knowledge_graph_id: str) -> bool:
        stmt = select(ExtractionRunModel.pause_requested).where(
            ExtractionRunModel.knowledge_graph_id == knowledge_graph_id
        )
        result = await self._session.execute(stmt)
        value = result.scalar_one_or_none()
        return bool(value)
