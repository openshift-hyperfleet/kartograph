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
