"""Helpers for deciding when sticky sessions should load JobPackage material."""

from __future__ import annotations

from extraction.application.job_package_gate import JobPackageGateDecision
from extraction.domain.value_objects import (
    IngestionReadinessSnapshot,
    SessionJobPackagePhase,
)


def should_materialize_job_packages(
    *,
    readiness: IngestionReadinessSnapshot,
    gate: JobPackageGateDecision,
) -> bool:
    """Return whether prepared JobPackage archives should be loaded into the workspace.

    UI-mode gates control whether chat must *wait* for JobPackage readiness.
    When prepared packages exist for the knowledge graph, materialize them even
    in modes that do not require the gate (e.g. Initial Schema Design).
    """
    if readiness.prepared_source_count > 0:
        return True
    return gate.phase != SessionJobPackagePhase.NOT_REQUIRED
