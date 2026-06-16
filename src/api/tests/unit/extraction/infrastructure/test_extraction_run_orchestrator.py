"""Tests for extraction run orchestrator baseline updates."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

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

    with patch(
        "extraction.infrastructure.extraction_run_orchestrator.reconcile_quiescent_extraction_run",
        new_callable=AsyncMock,
        return_value=(True, True),
    ) as reconcile:
        await orchestrator._maybe_finish_run(state)

    reconcile.assert_awaited_once()
    assert state.stop_event.is_set()
    assert "kg-001" not in orchestrator._active


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
