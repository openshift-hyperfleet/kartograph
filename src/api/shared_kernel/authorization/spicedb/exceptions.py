"""Exceptions for SpiceDB authorization operations."""


class AuthorizationError(Exception):
    """Base exception for authorization errors."""

    pass


class SpiceDBConnectionError(AuthorizationError):
    """Raised when connection to SpiceDB fails."""

    pass


class SpiceDBPermissionError(AuthorizationError):
    """Raised when a permission check or write operation fails."""

    pass
