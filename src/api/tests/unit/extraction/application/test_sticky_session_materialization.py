"""Unit tests for sticky session JobPackage materialization policy."""

from __future__ import annotations

from extraction.application.job_package_gate import resolve_job_package_gate
from extraction.application.sticky_session_materialization import should_materialize_job_packages
from extraction.domain.value_objects import (
    GraphManagementUiMode,
    IngestionReadinessSnapshot,
)


def test_schema_design_materializes_when_prepared_sources_exist() -> None:
    readiness = IngestionReadinessSnapshot(data_source_count=1, prepared_source_count=1)
    gate = resolve_job_package_gate(
        ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        readiness=readiness,
    )

    assert should_materialize_job_packages(readiness=readiness, gate=gate) is True


def test_schema_design_skips_materialization_without_prepared_sources() -> None:
    readiness = IngestionReadinessSnapshot(data_source_count=0, prepared_source_count=0)
    gate = resolve_job_package_gate(
        ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        readiness=readiness,
    )

    assert should_materialize_job_packages(readiness=readiness, gate=gate) is False


def test_extraction_jobs_materializes_when_gate_ready() -> None:
    readiness = IngestionReadinessSnapshot(data_source_count=2, prepared_source_count=2)
    gate = resolve_job_package_gate(
        ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        readiness=readiness,
    )

    assert should_materialize_job_packages(readiness=readiness, gate=gate) is True
