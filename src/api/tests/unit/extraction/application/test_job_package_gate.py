"""Unit tests for JobPackage gate resolution."""

from __future__ import annotations

from extraction.application.job_package_gate import (
    IngestionReadinessSnapshot,
    resolve_job_package_gate,
)
from extraction.domain.value_objects import (
    GraphManagementUiMode,
    SessionJobPackagePhase,
)


def test_schema_design_does_not_require_job_package() -> None:
    decision = resolve_job_package_gate(
        ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        readiness=IngestionReadinessSnapshot(0, 0),
    )
    assert decision.phase == SessionJobPackagePhase.NOT_REQUIRED


def test_extraction_jobs_waits_without_prepared_sources() -> None:
    decision = resolve_job_package_gate(
        ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        readiness=IngestionReadinessSnapshot(data_source_count=2, prepared_source_count=1),
    )
    assert decision.phase == SessionJobPackagePhase.AWAITING_PREPARE
    assert decision.wait_message is not None
    assert "JobPackage" in decision.wait_message


def test_extraction_jobs_ready_when_all_prepared() -> None:
    decision = resolve_job_package_gate(
        ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        readiness=IngestionReadinessSnapshot(data_source_count=2, prepared_source_count=2),
    )
    assert decision.phase == SessionJobPackagePhase.READY
