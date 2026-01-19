"""SpiceDB client dependency injection.

Provides SpiceDB client factory for dependency injection in FastAPI
endpoints and application services.

Note: Each call creates a new SpiceDBClient instance, but the underlying
gRPC AsyncClient is lazily initialized once per instance and handles
connection pooling internally. No singleton/locking needed.
"""

from __future__ import annotations

from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.spicedb.client import SpiceDBClient
from infrastructure.settings import get_spicedb_settings


def get_spicedb_client() -> AuthorizationProvider:
    """Get a SpiceDB authorization client.

    Creates a new SpiceDBClient instance configured from settings.
    The underlying gRPC connection is managed internally by the client
    with lazy initialization and connection pooling.

    Returns:
        Configured SpiceDB client implementing AuthorizationProvider protocol
    """
    settings = get_spicedb_settings()
    return SpiceDBClient(
        endpoint=settings.endpoint,
        preshared_key=settings.preshared_key.get_secret_value(),
        use_tls=settings.use_tls,
        cert_path=settings.cert_path,
    )
