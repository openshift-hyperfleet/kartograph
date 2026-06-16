"""Reconcile stuck extraction runs and advance extraction baselines."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from extraction.domain.extraction_job import ExtractionRunStatus
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from management.infrastructure.extraction_baseline_updater import (
    advance_extraction_baselines_for_knowledge_graph,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from extraction.infrastructure.extraction_run_orchestrator import (
        ExtractionRunOrchestrator,
    )


async def reconcile_quiescent_extraction_run(
    *,
    session: AsyncSession,
    knowledge_graph_id: str,
    orchestrator: ExtractionRunOrchestrator | None = None,
) -> tuple[bool, bool]:
    """Finish active runs and advance baselines when the job queue has drained.

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

    if run_was_active:
        await repo.upsert_run(
            knowledge_graph_id=knowledge_graph_id,
            status=ExtractionRunStatus.IDLE,
            worker_count=run.worker_count,
            pause_requested=False,
            completed_at=datetime.now(UTC),
        )

    baselines_updated = await advance_extraction_baselines_for_knowledge_graph(
        session=session,
        knowledge_graph_id=knowledge_graph_id,
    )

    if not run_was_active and baselines_updated <= 0:
        return False, False

    await session.commit()

    if orchestrator is not None and run_was_active:
        orchestrator.stop_active_run(knowledge_graph_id=knowledge_graph_id)

    return True, run_was_active
