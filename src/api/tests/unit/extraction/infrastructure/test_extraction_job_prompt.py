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
    assert "## Coverage default" in prompt
    assert "every schema property" in prompt
    assert "Feature: feature-a" in prompt
    assert "repo-a/features/a.feature" in prompt
    assert "job-context.json" in prompt
    assert "mutation-examples.jsonl" in prompt
    assert "properties_missing" in prompt
    assert "paths_not_found" in prompt
    assert "workload-graph-read.sh" in prompt
    assert "token-efficient" in prompt.lower() or "token-efficient" in prompt
    assert "set_properties" in prompt
    assert "properties you omit are preserved" in prompt


def test_build_extraction_job_prompt_mentions_graph_id_in_job_context() -> None:
    job = ExtractionJobRecord(
        id="job-row",
        knowledge_graph_id="kg-1",
        job_id="adapters_batch_0001_abcd1234",
        job_set_name="Adapter Enrichment",
        strategy="by_instances",
        status=ExtractionJobStatus.PENDING,
        order_index=0,
        description="Enrich adapter transport fields.",
        target_instances=(
            ExtractionTargetInstance(slug="cl_m_wrong_nest", entity_type="Adapter"),
        ),
    )

    prompt = build_extraction_job_prompt(job=job)

    assert "graph_id" in prompt
