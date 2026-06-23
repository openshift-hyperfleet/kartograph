"""Unit tests for maintenance extraction job prompts."""

from extraction.domain.extraction_job import (
    ExtractionJobRecord,
    ExtractionJobStatus,
    ExtractionTargetFile,
)
from extraction.infrastructure.maintenance_job_prompt import (
    build_maintenance_job_prompt,
)


def test_build_maintenance_job_prompt_documents_commit_layout() -> None:
    job = ExtractionJobRecord(
        id="job-row",
        knowledge_graph_id="kg-1",
        job_id="maintenance_batch_0001_abcd1234",
        job_set_name="maintenance",
        strategy="by_files",
        status=ExtractionJobStatus.PENDING,
        order_index=0,
        description="Update graph for upstream changes.",
        target_files=(
            ExtractionTargetFile(
                path="src/foo.go",
                repository_folder="hyperfleet-api",
                package_id="pkg-1",
                baseline_commit="defc3afd",
                head_commit="0b64088c",
                change_status="modified",
                patch="@@ diff @@",
            ),
        ),
    )

    prompt = build_maintenance_job_prompt(job=job)

    assert "repository-files/defc3afd/hyperfleet-api/src/foo.go" in prompt
    assert "repository-files/0b64088c/hyperfleet-api/src/foo.go" in prompt
    assert (
        "repository-files/diffs/defc3afd..0b64088c/hyperfleet-api/src/foo.go.patch"
        in prompt
    )
    assert "maintenance_commit_snapshots" not in prompt
    assert "sources-index.json layout.target_files" in prompt
    assert "Compare the baseline snapshot" in prompt
