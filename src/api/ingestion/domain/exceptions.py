"""Domain exceptions for the Ingestion bounded context."""


class SyncJobNotFoundError(Exception):
    """Raised when a SyncJob cannot be found by ID."""


class InvalidSyncJobStatusError(Exception):
    """Raised when an invalid status transition is attempted."""
