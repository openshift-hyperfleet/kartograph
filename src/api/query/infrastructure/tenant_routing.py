"""Per-tenant query routing for the Querying bounded context.

Implements the Per-Tenant Graph Routing requirement from
specs/query/query-execution.spec.md.

The system SHALL route all queries to the caller's tenant-specific AGE
graph (named ``tenant_{tenant_id}``). Queries directed at a tenant whose
graph has not yet been provisioned are rejected with a QueryExecutionError
before any database round-trip.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from query.domain.value_objects import (
    QueryExecutionError,
    QueryResultRow,
)
from query.ports.repositories import IQueryGraphRepository


@runtime_checkable
class _ConnectionFactory(Protocol):
    """Minimal protocol for the infrastructure ConnectionFactory.

    Defined here to avoid a static import of the infrastructure package
    inside the query.infrastructure layer (which would still be allowed
    by the architecture tests, but the Protocol keeps things clean and
    avoids any future circular-import risk).
    """

    def get_connection(self) -> Any:
        """Acquire a connection from the pool."""
        ...

    def return_connection(self, conn: Any) -> None:
        """Return a connection to the pool."""
        ...


class TenantAwareQueryGraphRepository(IQueryGraphRepository):
    """Tenant-routing decorator for IQueryGraphRepository.

    Wraps an inner repository (connected to a specific tenant's AGE graph)
    with a mandatory pre-execution check verifying that the tenant's graph
    exists. If the graph is absent, the query is rejected with a
    QueryExecutionError **before** any database round-trip.

    Security model:
        - The tenant's AGE graph name is always ``tenant_{tenant_id}``.
        - The existence check is the first operation performed, so
          mis-configured or stale tenants are caught immediately.
        - The inner repository enforces all other safeguards (read-only,
          timeout, LIMIT) independently of this class.

    Isolation guarantee:
        Each instance is constructed with a single ``tenant_id``. Queries
        from different tenants are served by separate instances, each
        connected to a different AGE graph. There is no shared state that
        could allow cross-tenant data access.

    Args:
        tenant_id:          ID of the tenant whose graph should be queried.
        inner_repository:   Pre-configured repository whose underlying
                            graph client is already targeting the tenant's
                            AGE graph (``tenant_{tenant_id}``).
        existence_check_fn: Callable that takes a graph name and returns
                            True if the graph exists in AGE, False otherwise.
                            In production this queries ``ag_catalog.ag_graph``.
                            In tests this is a lightweight fake.
    """

    def __init__(
        self,
        tenant_id: str,
        inner_repository: IQueryGraphRepository,
        existence_check_fn: Callable[[str], bool],
    ) -> None:
        self._tenant_id = tenant_id
        self._inner = inner_repository
        self._check_exists = existence_check_fn

    @property
    def graph_name(self) -> str:
        """The AGE graph name for this tenant."""
        return f"tenant_{self._tenant_id}"

    def execute_cypher(
        self,
        query: str,
        timeout_seconds: int = 30,
        max_rows: int = 1000,
    ) -> list[QueryResultRow]:
        """Execute a Cypher query routed to the tenant's AGE graph.

        Safeguard order:
            1. Graph existence check (primary gate — before reaching DB).
            2. All inner-repository safeguards: keyword blacklist,
               read-only transaction, timeout, LIMIT enforcement.

        Args:
            query:            Cypher query string.
            timeout_seconds:  Per-query database timeout in seconds.
            max_rows:         Maximum rows to return; default appended if
                              no LIMIT is present.

        Returns:
            List of result dictionaries.

        Raises:
            QueryExecutionError: If the tenant's AGE graph has not been
                provisioned. The inner repository is never contacted.
            QueryForbiddenError: If a mutation keyword is detected (raised
                by the inner repository).
            QueryTimeoutError: If the database cancels the statement (raised
                by the inner repository).
        """
        # Gate 1: Reject before reaching the database if the tenant graph
        # has not been provisioned (spec: Tenant graph not found scenario).
        if not self._check_exists(self.graph_name):
            raise QueryExecutionError(
                f"Tenant graph '{self.graph_name}' has not been provisioned. "
                "Ensure the tenant was created and its AGE graph is initialised.",
                query=query,
            )

        # Delegate to the inner repository for all remaining safeguards
        # and actual execution.
        return self._inner.execute_cypher(
            query=query,
            timeout_seconds=timeout_seconds,
            max_rows=max_rows,
        )


class AGEGraphExistenceChecker:
    """Checks AGE graph existence by querying ``ag_catalog.ag_graph``.

    This is the production implementation of the ``existence_check_fn``
    callable expected by :class:`TenantAwareQueryGraphRepository`.

    It acquires a raw connection from the pool, runs a single ``SELECT``
    against the AGE catalog, and immediately returns the connection.
    This is intentionally outside any AGE graph context — we only need
    a plain PostgreSQL connection to check the catalog.

    Args:
        connection_factory: Shared database connection pool factory.
    """

    def __init__(self, connection_factory: _ConnectionFactory) -> None:
        self._factory = connection_factory

    def __call__(self, graph_name: str) -> bool:
        """Return True if *graph_name* exists in ``ag_catalog.ag_graph``."""
        conn = self._factory.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
                    (graph_name,),
                )
                return cursor.fetchone() is not None
        finally:
            self._factory.return_connection(conn)
