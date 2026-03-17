"""Port exceptions for Management bounded context.

These exceptions represent domain-level errors that can occur during
repository operations. They should be caught and handled by the
application layer.
"""


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
