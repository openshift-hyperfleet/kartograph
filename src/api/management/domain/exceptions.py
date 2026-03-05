"""Domain exceptions for the Management bounded context."""


class InvalidKnowledgeGraphNameError(Exception):
    """Raised when a knowledge graph name fails validation."""

    pass


class InvalidDataSourceNameError(Exception):
    """Raised when a data source name fails validation."""

    pass


class InvalidScheduleError(Exception):
    """Raised when a schedule configuration is invalid."""

    pass


class AggregateDeletedError(Exception):
    """Raised when attempting to mutate a deleted aggregate."""

    pass


class InvalidIdentifierError(Exception):
    """Raised when a cross-context identifier (tenant_id, workspace_id, etc.) is empty or whitespace."""

    pass
