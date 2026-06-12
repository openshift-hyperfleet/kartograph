"""Unit tests for extraction job set configuration."""

from management.domain.extraction_job_config import (
    ExtractionJobConfigDocument,
    ExtractionJobSetDefinition,
    ExtractionJobSetStrategy,
)


def test_by_instances_requires_description_and_entity_type() -> None:
    job_set = ExtractionJobSetDefinition(
        name="component_tests",
        strategy=ExtractionJobSetStrategy.BY_INSTANCES,
        entity_type="ComponentTest",
        instances_per_job=4,
    )
    errors = job_set.validation_errors(entity_instance_counts={"ComponentTest": 10})
    assert any("description" in err.lower() for err in errors)


def test_disabled_job_set_skips_validation() -> None:
    job_set = ExtractionJobSetDefinition(
        name="disabled_set",
        strategy=ExtractionJobSetStrategy.BY_INSTANCES,
        enabled=False,
    )
    errors = job_set.validation_errors(entity_instance_counts={})
    assert errors == ()


def test_document_rejects_duplicate_job_set_names() -> None:
    document = ExtractionJobConfigDocument(
        version="1.0",
        job_sets=(
            ExtractionJobSetDefinition(
                name="set_a",
                strategy=ExtractionJobSetStrategy.BY_INSTANCES,
                entity_type="Feature",
                instances_per_job=2,
                description="Extract feature details",
            ),
            ExtractionJobSetDefinition(
                name="set_a",
                strategy=ExtractionJobSetStrategy.BY_INSTANCES,
                entity_type="Feature",
                instances_per_job=2,
                description="Duplicate name",
            ),
        ),
    )
    errors = document.validation_errors(entity_instance_counts={"Feature": 3})
    assert any("Duplicate" in err for err in errors)
