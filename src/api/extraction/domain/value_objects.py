"""Value objects for Extraction session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ExtractionSessionMode(StrEnum):
    """Workspace mode for extraction agent sessions."""

    SCHEMA_BOOTSTRAP = "schema_bootstrap"
    EXTRACTION_OPERATIONS = "extraction_operations"


class BootstrapIntakePath(StrEnum):
    """User-selected bootstrap onboarding path."""

    FIRST_PASS_SCHEMA_ATTEMPT = "first_pass_schema_attempt"
    GUIDED_CO_DESIGN = "guided_co_design"


class GraphManagementUiMode(StrEnum):
    """Graph-management UI mode overlay for chat skill framing."""

    INITIAL_SCHEMA_DESIGN = "initial-schema-design"
    EXTRACTION_JOBS = "extraction-jobs"
    ONE_OFF_MUTATIONS = "one-off-mutations"


class SessionJobPackagePhase(StrEnum):
    """JobPackage readiness phase for sticky session chat turns."""

    NOT_REQUIRED = "not_required"
    AWAITING_PREPARE = "awaiting_job_package"
    READY = "ready"


@dataclass(frozen=True)
class IngestionReadinessSnapshot:
    """Read-only ingestion prepare counts for a knowledge graph."""

    data_source_count: int
    prepared_source_count: int


@dataclass(frozen=True)
class ExtractionSessionRunMetric:
    """Run-level metrics linked to an extraction session."""

    sync_run_id: str
    mutation_log_id: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    token_usage_total: int | None = None
    cost_total_usd: float | None = None
    operation_counts: dict[str, int] = field(default_factory=dict)
