"""Unit tests for extraction job materialization."""

from infrastructure.management.extraction_job_materializer import (
    materialize_jobs_from_config,
)
from management.domain.extraction_job_config import (
    ExtractionJobConfigDocument,
    ExtractionJobSetDefinition,
    ExtractionJobSetStrategy,
)


def test_materialize_by_instances_batches_graph_nodes() -> None:
    config = ExtractionJobConfigDocument(
        version="1.0",
        job_sets=(
            ExtractionJobSetDefinition(
                name="features",
                strategy=ExtractionJobSetStrategy.BY_INSTANCES,
                entity_type="Feature",
                instances_per_job=2,
                description="Extract acceptance criteria for each feature instance.",
            ),
        ),
    )
    graph_data = {
        "nodes": [
            {
                "knowledge_graph_id": "kg-1",
                "type": "Feature",
                "slug": "feature-a",
            },
            {
                "knowledge_graph_id": "kg-1",
                "type": "Feature",
                "slug": "feature-b",
            },
            {
                "knowledge_graph_id": "kg-1",
                "type": "Feature",
                "slug": "feature-c",
            },
        ],
        "edges": [],
    }

    jobs = materialize_jobs_from_config(
        knowledge_graph_id="kg-1",
        config=config,
        graph_data=graph_data,
    )

    assert len(jobs) == 2
    assert jobs[0].target_instances[0].slug == "feature-a"
    assert jobs[0].description.startswith("Extract acceptance")
    assert all(job.status.value == "pending" for job in jobs)


def test_materialize_skips_disabled_job_sets() -> None:
    config = ExtractionJobConfigDocument(
        version="1.0",
        job_sets=(
            ExtractionJobSetDefinition(
                name="disabled",
                strategy=ExtractionJobSetStrategy.BY_INSTANCES,
                entity_type="Feature",
                instances_per_job=1,
                description="Should not materialize.",
                enabled=False,
            ),
        ),
    )
    graph_data = {
        "nodes": [
            {
                "knowledge_graph_id": "kg-1",
                "type": "Feature",
                "slug": "feature-a",
            },
        ],
        "edges": [],
    }

    jobs = materialize_jobs_from_config(
        knowledge_graph_id="kg-1",
        config=config,
        graph_data=graph_data,
    )

    assert jobs == []
