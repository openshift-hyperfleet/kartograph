"""Unit tests for extraction job prompt building."""

from extraction.domain.extraction_job import (
    ExtractionJobRecord,
    ExtractionJobStatus,
    ExtractionTargetFile,
    ExtractionTargetInstance,
)
from extraction.infrastructure.extraction_job_prompt import build_extraction_job_prompt


def test_build_extraction_job_prompt_includes_instances_and_files() -> None:
    job = ExtractionJobRecord(
        id="job-row",
        knowledge_graph_id="kg-1",
        job_id="features_batch_0001_abcd1234",
        job_set_name="features",
        strategy="by_instances",
        status=ExtractionJobStatus.PENDING,
        order_index=0,
        description="Extract acceptance criteria.",
        target_instances=(
            ExtractionTargetInstance(slug="feature-a", entity_type="Feature"),
        ),
        target_files=(
            ExtractionTargetFile(
                path="features/a.feature",
                repository_folder="repo-a",
                package_id="pkg-1",
            ),
        ),
    )

    prompt = build_extraction_job_prompt(job=job)

    assert "Extract acceptance criteria." in prompt
    assert "Feature: feature-a" in prompt
    assert "repo-a/features/a.feature" in prompt
    assert "job-context.json" in prompt
