"""Reconcile stuck extraction runs and advance extraction baselines."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Awaitable, Callable, TYPE_CHECKING

from extraction.domain.extraction_job import ExtractionRunStatus
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from extraction.infrastructure.extraction_run_orchestrator import (
        ExtractionRunOrchestrator,
    )

AdvanceBaselines = Callable[..., Awaitable[int]]


async def reconcile_quiescent_extraction_run(
    *,
    session: AsyncSession,
    knowledge_graph_id: str,
    orchestrator: ExtractionRunOrchestrator | None = None,
    advance_baselines: AdvanceBaselines | None = None,
) -> tuple[bool, bool]:
    """Finish active runs and advance baselines when the job queue has drained.

    Baselines advance only after an active extraction run quiesces with no failed
    jobs remaining. Idle polls with an already-idle run do not move baselines.

    Returns:
        A tuple of (reconciled, run_was_active). ``reconciled`` is True when the
        database was updated. ``run_was_active`` is True when an active run row
        was transitioned to idle (callers should stop in-memory orchestrator
        workers when this is True).
    """
    repo = ExtractionJobRepository(session)
    counts = await repo.count_by_status(knowledge_graph_id=knowledge_graph_id)
    if counts.get("pending", 0) > 0 or counts.get("in_progress", 0) > 0:
        return False, False

    run = await repo.get_run(knowledge_graph_id=knowledge_graph_id)
    run_was_active = run is not None and run.status != ExtractionRunStatus.IDLE
    if not run_was_active:
        return False, False

    await repo.upsert_run(
        knowledge_graph_id=knowledge_graph_id,
        status=ExtractionRunStatus.IDLE,
        worker_count=run.worker_count,
        pause_requested=False,
        completed_at=datetime.now(UTC),
    )

    if counts.get("failed", 0) == 0:
        advancer = advance_baselines
        if advancer is None:
            from infrastructure.management.extraction_baseline_hook import (
                get_extraction_baseline_advancer,
            )

            advancer = get_extraction_baseline_advancer()
        if advancer is not None:
            await advancer(
                session=session,
                knowledge_graph_id=knowledge_graph_id,
            )

    await session.commit()

    if orchestrator is not None:
        orchestrator.stop_active_run(knowledge_graph_id=knowledge_graph_id)

    return True, run_was_active
