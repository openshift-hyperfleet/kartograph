"""Unit tests for stub extraction job runner."""

import pytest

from extraction.domain.extraction_job import (
    ExtractionJobRecord,
    ExtractionJobStatus,
    ExtractionTargetFile,
)
from extraction.infrastructure.stub_extraction_job_runner import StubExtractionJobRunner


@pytest.mark.asyncio
async def test_stub_runner_returns_metrics_for_file_targets() -> None:
    runner = StubExtractionJobRunner()
    job = ExtractionJobRecord(
        id="job-row",
        knowledge_graph_id="kg-1",
        job_id="docs_batch_0001_abcd1234",
        job_set_name="docs",
        strategy="by_files",
        status=ExtractionJobStatus.PENDING,
        order_index=0,
        description="Extract docs.",
        target_files=(
            ExtractionTargetFile(path="a.md", repository_folder="repo", package_id="pkg"),
            ExtractionTargetFile(path="b.md", repository_folder="repo", package_id="pkg"),
        ),
    )

    metrics = await runner.run(job, tenant_id="tenant-1")

    assert metrics["input_tokens"] == 200
    assert metrics["entities_modified"] == 2
