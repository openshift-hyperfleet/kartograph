"""Background orchestrator for parallel extraction job execution."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from extraction.infrastructure.extraction_job_executor import ExtractionJobExecutor
from extraction.domain.extraction_job import ExtractionRunStatus
from extraction.infrastructure.extraction_run_reconciliation import (
    reconcile_quiescent_extraction_run,
)
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class _OrchestratorState:
    knowledge_graph_id: str
    tenant_id: str
    worker_count: int
    tasks: list[asyncio.Task[None]] = field(default_factory=list)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)


class ExtractionRunOrchestrator:
    """Manage extraction run lifecycle and worker pool for one knowledge graph."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        job_executor: ExtractionJobExecutor | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._job_executor = job_executor or ExtractionJobExecutor(
            session_factory=session_factory
        )
        self._active: dict[str, _OrchestratorState] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        worker_count: int,
    ) -> None:
        async with self._lock:
            requested = max(1, worker_count)
            existing = self._active.get(knowledge_graph_id)
            if existing and not existing.stop_event.is_set():
                if existing.worker_count < requested:
                    self._spawn_workers(existing, target_count=requested)
                    async with self._session_factory() as session:
                        repo = ExtractionJobRepository(session)
                        await repo.upsert_run(
                            knowledge_graph_id=knowledge_graph_id,
                            status=ExtractionRunStatus.RUNNING,
                            worker_count=requested,
                            pause_requested=False,
                        )
                        await session.commit()
                return

            state = _OrchestratorState(
                knowledge_graph_id=knowledge_graph_id,
                tenant_id=tenant_id,
                worker_count=requested,
            )
            self._active[knowledge_graph_id] = state

            async with self._session_factory() as session:
                repo = ExtractionJobRepository(session)
                await repo.upsert_run(
                    knowledge_graph_id=knowledge_graph_id,
                    status=ExtractionRunStatus.RUNNING,
                    worker_count=state.worker_count,
                    pause_requested=False,
                    orchestrator_pid=os.getpid(),
                    started_at=datetime.now(UTC),
                    completed_at=None,
                )
                await session.commit()

            self._spawn_workers(state, target_count=state.worker_count)

    def _spawn_workers(self, state: _OrchestratorState, *, target_count: int) -> None:
        """Start worker tasks until the pool reaches target_count."""
        while len(state.tasks) < target_count:
            worker_index = len(state.tasks) + 1
            state.tasks.append(
                asyncio.create_task(self._worker_loop(state, worker_index=worker_index))
            )
        state.worker_count = target_count

    async def request_pause(self, *, knowledge_graph_id: str) -> None:
        async with self._session_factory() as session:
            repo = ExtractionJobRepository(session)
            await repo.set_pause_requested(
                knowledge_graph_id=knowledge_graph_id, pause_requested=True
            )
            await repo.upsert_run(
                knowledge_graph_id=knowledge_graph_id,
                status=ExtractionRunStatus.PAUSING,
                worker_count=1,
                pause_requested=True,
            )
            await session.commit()

    async def stop_workers(self, *, knowledge_graph_id: str) -> None:
        """Cancel worker tasks without changing job rows (for reset-to-pending flows)."""
        state = self._active.get(knowledge_graph_id)
        if state is None:
            return
        state.stop_event.set()
        for task in state.tasks:
            task.cancel()
        self._active.pop(knowledge_graph_id, None)

    async def halt(self, *, knowledge_graph_id: str) -> None:
        state = self._active.get(knowledge_graph_id)
        if state is not None:
            state.stop_event.set()
            for task in state.tasks:
                task.cancel()
            self._active.pop(knowledge_graph_id, None)

        async with self._session_factory() as session:
            repo = ExtractionJobRepository(session)
            await repo.mark_in_progress_failed(
                knowledge_graph_id=knowledge_graph_id,
                error_message="Extraction halted by operator",
            )
            await repo.upsert_run(
                knowledge_graph_id=knowledge_graph_id,
                status=ExtractionRunStatus.HALTED,
                worker_count=1,
                pause_requested=False,
                completed_at=datetime.now(UTC),
            )
            await session.commit()

    async def _worker_loop(
        self, state: _OrchestratorState, *, worker_index: int
    ) -> None:
        worker_id = f"worker-{worker_index:02d}"
        try:
            while not state.stop_event.is_set():
                async with self._session_factory() as session:
                    repo = ExtractionJobRepository(session)
                    if await repo.is_pause_requested(
                        knowledge_graph_id=state.knowledge_graph_id
                    ):
                        await repo.upsert_run(
                            knowledge_graph_id=state.knowledge_graph_id,
                            status=ExtractionRunStatus.PAUSED,
                            worker_count=state.worker_count,
                            pause_requested=True,
                            completed_at=datetime.now(UTC),
                        )
                        await session.commit()
                        state.stop_event.set()
                        break

                    job = await repo.claim_next_pending_job(
                        knowledge_graph_id=state.knowledge_graph_id,
                        worker_id=worker_id,
                    )
                    if job is None:
                        counts = await repo.count_by_status(
                            knowledge_graph_id=state.knowledge_graph_id
                        )
                        if counts.get("in_progress", 0) > 0:
                            await session.commit()
                            await asyncio.sleep(2)
                            continue
                        if counts.get("pending", 0) > 0:
                            await session.commit()
                            await asyncio.sleep(2)
                            continue
                        await session.commit()
                        await self._maybe_finish_run(state)
                        break
                    await session.commit()

                try:
                    metrics = await self._job_executor.execute(
                        job,
                        tenant_id=state.tenant_id,
                    )
                except Exception as exc:
                    logger.exception(
                        "Extraction job %s failed on worker %s",
                        job.job_id,
                        worker_id,
                    )
                    async with self._session_factory() as session:
                        repo = ExtractionJobRepository(session)
                        await repo.mark_job_failed(
                            knowledge_graph_id=state.knowledge_graph_id,
                            job_id=job.job_id,
                            error_message=str(exc),
                        )
                        await session.commit()
                    continue

                async with self._session_factory() as session:
                    repo = ExtractionJobRepository(session)
                    await repo.mark_job_completed(
                        knowledge_graph_id=state.knowledge_graph_id,
                        job_id=job.job_id,
                        metrics=metrics,
                    )
                    await session.commit()
        except asyncio.CancelledError:
            return

    async def _maybe_finish_run(self, state: _OrchestratorState) -> None:
        async with self._session_factory() as session:
            _, run_was_active = await reconcile_quiescent_extraction_run(
                session=session,
                knowledge_graph_id=state.knowledge_graph_id,
            )
            if run_was_active:
                state.stop_event.set()
                self._active.pop(state.knowledge_graph_id, None)

    def stop_active_run(self, *, knowledge_graph_id: str) -> None:
        """Stop in-memory workers for a knowledge graph run."""
        state = self._active.get(knowledge_graph_id)
        if state is None:
            return
        state.stop_event.set()
        for task in state.tasks:
            task.cancel()
        self._active.pop(knowledge_graph_id, None)

    def is_live(self, *, knowledge_graph_id: str) -> bool:
        state = self._active.get(knowledge_graph_id)
        return state is not None and not state.stop_event.is_set()

    async def ensure_workers_for_pending(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> None:
        """Start worker tasks when pending jobs exist but the pool has stopped."""
        if self.is_live(knowledge_graph_id=knowledge_graph_id):
            return

        async with self._session_factory() as session:
            repo = ExtractionJobRepository(session)
            counts = await repo.count_by_status(knowledge_graph_id=knowledge_graph_id)
            run = await repo.get_run(knowledge_graph_id=knowledge_graph_id)

        pending = counts.get("pending", 0)
        if pending <= 0:
            return
        if run is None or run.status not in {
            ExtractionRunStatus.RUNNING,
            ExtractionRunStatus.PAUSING,
        }:
            return

        await self.start(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            worker_count=run.worker_count,
        )


_orchestrator_singleton: ExtractionRunOrchestrator | None = None


def get_extraction_run_orchestrator(
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> ExtractionRunOrchestrator:
    global _orchestrator_singleton
    if _orchestrator_singleton is None:
        _orchestrator_singleton = ExtractionRunOrchestrator(
            session_factory=session_factory
        )
    return _orchestrator_singleton
