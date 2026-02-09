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


class DuplicateAPIKeyNameError(Exception):
    """Raised when attempting to create an API key with a name that already exists.

    This exception indicates that the business rule of unique API key names
    per user within a tenant has been violated.
    """

    pass


class APIKeyNotFoundError(Exception):
    """Raised when an API key cannot be found.

    This exception is raised when attempting to retrieve or operate on
    an API key that does not exist.
    """

    pass


class APIKeyAlreadyRevokedError(Exception):
    """Raised when attempting to revoke an API key that is already revoked.

    This exception indicates that the API key has already been revoked
    and cannot be revoked again.
    """

    pass


class UnauthorizedError(Exception):
    """Raised when a user lacks permission to perform an operation.

    This exception indicates that authorization checks have failed.
    The application layer should handle this and return appropriate
    HTTP 403 responses without exposing internal details.
    """

    pass


class DuplicateWorkspaceNameError(Exception):
    """Raised when workspace name already exists in tenant.

    This exception indicates that the business rule of unique workspace
    names per tenant has been violated. The application layer should
    handle this and provide appropriate feedback to the user.
    """

    pass


class CannotDeleteRootWorkspaceError(Exception):
    """Raised when attempting to delete root workspace.

    Root workspaces are auto-created with tenants and serve as the
    default workspace. They cannot be deleted while the tenant exists.
    """

    pass


class WorkspaceHasChildrenError(Exception):
    """Raised when attempting to delete workspace with children.

    A workspace cannot be deleted if it has child workspaces. The
    children must be deleted or reparented first.
    """

    pass
