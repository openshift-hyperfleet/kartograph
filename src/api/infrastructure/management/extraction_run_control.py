"""Composition-root helpers for management routes that control extraction runs."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def reconcile_data_source_extraction_run(
    *,
    session: AsyncSession,
    knowledge_graph_id: str,
    session_factory: async_sessionmaker,
) -> tuple[bool, bool]:
    """Reconcile an idle extraction run and advance baselines when appropriate."""
    from extraction.infrastructure.extraction_run_orchestrator import (
        get_extraction_run_orchestrator,
    )
    from extraction.infrastructure.extraction_run_reconciliation import (
        reconcile_quiescent_extraction_run,
    )
    from management.infrastructure.extraction_baseline_updater import (
        advance_extraction_baselines_for_knowledge_graph,
    )

    orchestrator = get_extraction_run_orchestrator(
        session_factory=session_factory,
    )

    async def _advance_baselines(
        *, session: AsyncSession, knowledge_graph_id: str
    ) -> int:
        return await advance_extraction_baselines_for_knowledge_graph(
            session=session,
            knowledge_graph_id=knowledge_graph_id,
        )

    return await reconcile_quiescent_extraction_run(
        session=session,
        knowledge_graph_id=knowledge_graph_id,
        orchestrator=orchestrator,
        advance_baselines=_advance_baselines,
    )
