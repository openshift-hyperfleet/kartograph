"""Domain exceptions for IAM bounded context.

These exceptions represent domain-level errors that can occur during
repository operations. They should be caught and handled by the
application layer.
"""


class DuplicateGroupNameError(Exception):
    """Raised when attempting to create a group with a name that already exists in the tenant.

    This exception indicates that the business rule of unique group names
    per tenant has been violated. The application layer should handle this
    and provide appropriate feedback to the user.
    """

    pass


class DuplicateTenantNameError(Exception):
    """Raised when attempting to create a tenant with a name that already exists.

    This exception indicates that the business rule of globally unique tenant
    names has been violated. The application layer should handle this and
    provide appropriate feedback to the user.
    """

    pass
