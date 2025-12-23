"""SpiceDB client implementation for authorization.

This module provides the SpiceDB client that implements the AuthorizationProvider
protocol for fine-grained access control.
"""

from shared_kernel.authorization.spicedb.client import SpiceDBClient
from shared_kernel.authorization.spicedb.exceptions import (
    AuthorizationError,
    SpiceDBConnectionError,
    SpiceDBPermissionError,
)

__all__ = [
    "SpiceDBClient",
    "AuthorizationError",
    "SpiceDBConnectionError",
    "SpiceDBPermissionError",
]
