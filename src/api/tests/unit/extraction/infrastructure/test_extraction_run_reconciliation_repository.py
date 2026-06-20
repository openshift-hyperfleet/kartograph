"""Tests for reconciliation repository wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from extraction.infrastructure.extraction_run_reconciliation import (
    reconcile_quiescent_extraction_run,
)


@pytest.mark.asyncio
async def test_reconcile_skips_baseline_advance_when_no_active_run() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.count_by_status.return_value = {"pending": 0, "in_progress": 0, "failed": 0}
    repo.get_run.return_value = None

    with (
        patch(
            "extraction.infrastructure.extraction_run_reconciliation.ExtractionJobRepository",
            return_value=repo,
        ),
        patch(
            "extraction.infrastructure.extraction_run_reconciliation.advance_extraction_baselines_for_knowledge_graph",
            new_callable=AsyncMock,
        ) as advance_baselines,
    ):
        reconciled, run_was_active = await reconcile_quiescent_extraction_run(
            session=session,
            knowledge_graph_id="kg-001",
        )

    assert reconciled is False
    assert run_was_active is False
    advance_baselines.assert_not_awaited()
    session.commit.assert_not_awaited()
