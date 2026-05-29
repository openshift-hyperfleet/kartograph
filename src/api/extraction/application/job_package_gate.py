"""Pure helpers for JobPackage readiness gating in chat turns."""

from __future__ import annotations

from dataclasses import dataclass

from extraction.domain.value_objects import (
    GraphManagementUiMode,
    IngestionReadinessSnapshot,
    SessionJobPackagePhase,
)


@dataclass(frozen=True)
class JobPackageGateDecision:
    """Resolved JobPackage gate for one chat turn."""

    phase: SessionJobPackagePhase
    wait_message: str | None = None


def resolve_job_package_gate(
    *,
    ui_mode: GraphManagementUiMode,
    readiness: IngestionReadinessSnapshot,
) -> JobPackageGateDecision:
    """Return whether a chat turn must wait for JobPackage context."""
    if ui_mode in {
        GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        GraphManagementUiMode.ONE_OFF_MUTATIONS,
    }:
        return JobPackageGateDecision(phase=SessionJobPackagePhase.NOT_REQUIRED)

    if readiness.data_source_count == 0:
        return JobPackageGateDecision(
            phase=SessionJobPackagePhase.AWAITING_PREPARE,
            wait_message=(
                "Waiting for a connected data source. Add and prepare data sources "
                "under Data sources before extraction job chat can run."
            ),
        )

    if readiness.prepared_source_count < readiness.data_source_count:
        return JobPackageGateDecision(
            phase=SessionJobPackagePhase.AWAITING_PREPARE,
            wait_message=(
                "Waiting for JobPackage ingestion context. Prepare all data sources "
                f"({readiness.prepared_source_count}/{readiness.data_source_count} ready) "
                "so the sticky session container can load repository files."
            ),
        )

    return JobPackageGateDecision(phase=SessionJobPackagePhase.READY)
