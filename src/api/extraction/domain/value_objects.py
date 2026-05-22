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
