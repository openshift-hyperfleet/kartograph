"""Value objects for Extraction session lifecycle."""

from enum import StrEnum


class ExtractionSessionMode(StrEnum):
    """Workspace mode for extraction agent sessions."""

    SCHEMA_BOOTSTRAP = "schema_bootstrap"
    EXTRACTION_OPERATIONS = "extraction_operations"


class BootstrapIntakePath(StrEnum):
    """User-selected bootstrap onboarding path."""

    FIRST_PASS_SCHEMA_ATTEMPT = "first_pass_schema_attempt"
    GUIDED_CO_DESIGN = "guided_co_design"

