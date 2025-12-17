"""Shared infrastructure dependencies.

Provides ONLY raw database infrastructure resources (connection pools).
Does NOT import from bounded contexts to maintain DDD boundaries.
"""

from functools import lru_cache

from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import get_database_settings


@lru_cache
def get_age_connection_pool() -> ConnectionPool:
    """Get application-scoped AGE connection pool (singleton).

    The pool is thread-safe and shared across all requests.

    Returns:
        ConnectionPool instance configured for Apache AGE.
    """
    settings = get_database_settings()
    return ConnectionPool(settings)
