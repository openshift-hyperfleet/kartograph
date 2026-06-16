"""Tests for quiescent extraction run reconciliation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from extraction.domain.extraction_job import ExtractionRunRecord, ExtractionRunStatus
from extraction.infrastructure.extraction_run_reconciliation import (
    reconcile_quiescent_extraction_run,
)


@pytest.mark.asyncio
async def test_reconcile_skips_when_jobs_remain() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.count_by_status.return_value = {"pending": 1, "in_progress": 0}

    with patch(
        "extraction.infrastructure.extraction_run_reconciliation.ExtractionJobRepository",
        return_value=repo,
    ):
        reconciled, run_was_active = await reconcile_quiescent_extraction_run(
            session=session,
            knowledge_graph_id="kg-001",
        )

    assert reconciled is False
    assert run_was_active is False
    repo.upsert_run.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_finishes_active_run_and_advances_baselines() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.count_by_status.return_value = {"pending": 0, "in_progress": 0}
    repo.get_run.return_value = ExtractionRunRecord(
        id="run-001",
        knowledge_graph_id="kg-001",
        status=ExtractionRunStatus.RUNNING,
        worker_count=10,
        pause_requested=False,
        started_at=None,
        completed_at=None,
        orchestrator_pid=None,
    )
    orchestrator = MagicMock()

    with (
        patch(
            "extraction.infrastructure.extraction_run_reconciliation.ExtractionJobRepository",
            return_value=repo,
        ),
        patch(
            "extraction.infrastructure.extraction_run_reconciliation.advance_extraction_baselines_for_knowledge_graph",
            new_callable=AsyncMock,
            return_value=2,
        ) as advance_baselines,
    ):
        reconciled, run_was_active = await reconcile_quiescent_extraction_run(
            session=session,
            knowledge_graph_id="kg-001",
            orchestrator=orchestrator,
        )

    assert reconciled is True
    assert run_was_active is True
    repo.upsert_run.assert_awaited_once()
    assert repo.upsert_run.await_args.kwargs["status"] == ExtractionRunStatus.IDLE
    advance_baselines.assert_awaited_once_with(
        session=session,
        knowledge_graph_id="kg-001",
    )
    session.commit.assert_awaited_once()
    orchestrator.stop_active_run.assert_called_once_with(knowledge_graph_id="kg-001")


@pytest.mark.asyncio
async def test_reconcile_advances_baselines_when_run_already_idle() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.count_by_status.return_value = {"pending": 0, "in_progress": 0}
    repo.get_run.return_value = ExtractionRunRecord(
        id="run-001",
        knowledge_graph_id="kg-001",
        status=ExtractionRunStatus.IDLE,
        worker_count=0,
        pause_requested=False,
        started_at=None,
        completed_at=None,
        orchestrator_pid=None,
    )

    with (
        patch(
            "extraction.infrastructure.extraction_run_reconciliation.ExtractionJobRepository",
            return_value=repo,
        ),
        patch(
            "extraction.infrastructure.extraction_run_reconciliation.advance_extraction_baselines_for_knowledge_graph",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        reconciled, run_was_active = await reconcile_quiescent_extraction_run(
            session=session,
            knowledge_graph_id="kg-001",
        )

    assert reconciled is True
    assert run_was_active is False
    repo.upsert_run.assert_not_awaited()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_noop_when_queue_and_baselines_are_current() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.count_by_status.return_value = {"pending": 0, "in_progress": 0}
    repo.get_run.return_value = ExtractionRunRecord(
        id="run-001",
        knowledge_graph_id="kg-001",
        status=ExtractionRunStatus.IDLE,
        worker_count=0,
        pause_requested=False,
        started_at=None,
        completed_at=None,
        orchestrator_pid=None,
    )

    with (
        patch(
            "extraction.infrastructure.extraction_run_reconciliation.ExtractionJobRepository",
            return_value=repo,
        ),
        patch(
            "extraction.infrastructure.extraction_run_reconciliation.advance_extraction_baselines_for_knowledge_graph",
            new_callable=AsyncMock,
            return_value=0,
        ),
    ):
        reconciled, run_was_active = await reconcile_quiescent_extraction_run(
            session=session,
            knowledge_graph_id="kg-001",
        )

    assert reconciled is False
    assert run_was_active is False
    session.commit.assert_not_awaited()
