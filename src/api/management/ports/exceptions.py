"""Port exceptions for Management bounded context.

These exceptions represent domain-level errors that can occur during
repository operations. They should be caught and handled by the
application layer.
"""


class KnowledgeGraphNotFoundError(Exception):
    """Raised when a knowledge graph cannot be found or is inaccessible.

    This exception indicates that a requested knowledge graph does not exist
    in the given tenant scope. The presentation layer maps this to HTTP 404.
    """

    pass


class DuplicateKnowledgeGraphNameError(Exception):
    """Raised when a knowledge graph name already exists in the tenant.

    This exception indicates that the business rule of unique knowledge graph
    names per tenant has been violated. The application layer should handle
    this and provide appropriate feedback to the user.
    """

    pass


class DuplicateDataSourceNameError(Exception):
    """Raised when a data source name already exists in the knowledge graph.

    This exception indicates that the business rule of unique data source
    names per knowledge graph has been violated. The application layer
    should handle this and provide appropriate feedback to the user.
    """

    pass


class UnauthorizedError(Exception):
    """Raised when a user lacks permission to perform an operation.

    This exception indicates that authorization checks have failed.
    The application layer should handle this and return appropriate
    HTTP 403 responses without exposing internal details.
    """

    pass
