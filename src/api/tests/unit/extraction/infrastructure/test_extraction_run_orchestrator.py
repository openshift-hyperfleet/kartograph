"""Tests for extraction run orchestrator baseline updates."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from extraction.domain.extraction_job import ExtractionRunStatus
from extraction.infrastructure.extraction_run_orchestrator import (
    ExtractionRunOrchestrator,
    _OrchestratorState,
)


@pytest.mark.asyncio
async def test_maybe_finish_run_advances_extraction_baselines_for_kg() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    @asynccontextmanager
    async def session_context():
        yield session

    session_factory = lambda: session_context()

    orchestrator = ExtractionRunOrchestrator(session_factory=session_factory)
    state = _OrchestratorState(
        knowledge_graph_id="kg-001",
        tenant_id="tenant-001",
        worker_count=2,
    )

    repo = AsyncMock()
    repo.count_by_status.return_value = {"pending": 0, "in_progress": 0}

    with (
        patch(
            "extraction.infrastructure.extraction_run_orchestrator.ExtractionJobRepository",
            return_value=repo,
        ),
        patch(
            "extraction.infrastructure.extraction_run_orchestrator.advance_extraction_baselines_for_knowledge_graph",
            new_callable=AsyncMock,
        ) as advance_baselines,
    ):
        await orchestrator._maybe_finish_run(state)

    repo.upsert_run.assert_awaited_once()
    assert repo.upsert_run.await_args.kwargs["status"] == ExtractionRunStatus.IDLE
    advance_baselines.assert_awaited_once_with(
        session=session,
        knowledge_graph_id="kg-001",
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_scales_up_worker_tasks_when_run_is_already_live() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    @asynccontextmanager
    async def session_context():
        yield session

    session_factory = lambda: session_context()

    orchestrator = ExtractionRunOrchestrator(session_factory=session_factory)
    state = _OrchestratorState(
        knowledge_graph_id="kg-001",
        tenant_id="tenant-001",
        worker_count=10,
    )
    state.tasks = [AsyncMock() for _ in range(10)]
    orchestrator._active["kg-001"] = state

    with (
        patch(
            "extraction.infrastructure.extraction_run_orchestrator.ExtractionJobRepository",
        ) as repo_cls,
        patch.object(orchestrator, "_worker_loop", new_callable=AsyncMock),
    ):
        repo_cls.return_value = AsyncMock()
        await orchestrator.start(
            tenant_id="tenant-001",
            knowledge_graph_id="kg-001",
            worker_count=20,
        )

    assert state.worker_count == 20
    assert len(state.tasks) == 20
