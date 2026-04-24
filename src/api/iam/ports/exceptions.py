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


class ParentWorkspaceNotFoundError(Exception):
    """Raised when the specified parent workspace does not exist.

    This exception allows the presentation layer to normalize the error
    as 404 without parsing free-form message text. A missing parent is
    indistinguishable from an unauthorized parent — both surface as 404
    to callers so workspace existence is not leaked.
    """

    pass


class ParentWorkspaceCrossTenantError(Exception):
    """Raised when the specified parent workspace belongs to a different tenant.

    Cross-tenant parent access is treated the same as a missing parent:
    the route returns 404 so that tenant boundaries are not disclosed
    through error codes.
    """

    pass


class ProvisioningConflictError(Exception):
    """Raised when JIT user provisioning fails due to a username conflict.

    Two SSO users with the same ``preferred_username`` claim cannot both be
    provisioned in the same Kartograph instance because usernames must be
    globally unique. This exception deliberately hides database internals
    (e.g. IntegrityError / unique-constraint violations) and exposes only
    a user-friendly message.

    Attributes:
        username: The conflicting username that triggered the error.
    """

    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(
            f"Username '{username}' is already taken by another account. "
            "Contact your administrator if you believe this is an error."
        )
