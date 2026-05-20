"""Value objects for Extraction session lifecycle."""

from enum import StrEnum


class ExtractionSessionMode(StrEnum):
    """Workspace mode for extraction agent sessions."""

    SCHEMA_BOOTSTRAP = "schema_bootstrap"
    EXTRACTION_OPERATIONS = "extraction_operations"

