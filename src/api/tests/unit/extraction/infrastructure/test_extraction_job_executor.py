"""Tests for extraction job executor session lifecycle."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionJobStatus
from extraction.domain.prepared_extraction_job_run import PreparedExtractionJobRun
from extraction.infrastructure.extraction_job_executor import ExtractionJobExecutor


def _job() -> ExtractionJobRecord:
    return ExtractionJobRecord(
        id="row-1",
        knowledge_graph_id="kg-1",
        job_id="job-001",
        job_set_name="set-a",
        strategy="by_instances",
        status=ExtractionJobStatus.IN_PROGRESS,
        order_index=0,
        description="extract",
    )


@pytest.mark.asyncio
async def test_execute_releases_db_session_before_run_prepared() -> None:
    session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    @asynccontextmanager
    async def session_factory():
        yield session

    runner = MagicMock()
    runner.prepare_for_run = AsyncMock(
        return_value=PreparedExtractionJobRun(workdir=Path("/tmp/job"), prompt="go")
    )
    runner.run_prepared = AsyncMock(return_value={"write_ops": 1})
    runner.run = AsyncMock()

    with (
        patch(
            "extraction.infrastructure.extraction_job_executor.get_extraction_workload_runtime_settings",
        ) as settings_mock,
        patch(
            "extraction.infrastructure.extraction_job_executor.create_extraction_job_runner",
            return_value=runner,
        ),
    ):
        settings = settings_mock.return_value
        settings.job_runner = "openshell"
        executor = ExtractionJobExecutor(session_factory=session_factory)
        result = await executor.execute(_job(), tenant_id="tenant-1")

    assert result == {"write_ops": 1}
    runner.prepare_for_run.assert_awaited_once()
    runner.run_prepared.assert_awaited_once()
    runner.run.assert_not_called()
