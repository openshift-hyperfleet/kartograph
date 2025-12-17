"""Domain probes for infrastructure observability.

Domain probes provide a high-level instrumentation API oriented around
domain semantics, keeping infrastructure code clean and testable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from infrastructure.observability.context import ObservationContext


class ConnectionProbe(Protocol):
    """Domain probe for database connection observability.

    This probe captures domain-significant events related to database
    connections without exposing logging implementation details.
    """

    def connection_established(self, host: str, database: str) -> None:
        """Record that a database connection was successfully established."""
        ...

    def connection_failed(self, host: str, database: str, error: Exception) -> None:
        """Record that a database connection attempt failed."""
        ...

    def connection_closed(self) -> None:
        """Record that a database connection was closed."""
        ...

    def pool_initialized(self, min_conn: int, max_conn: int) -> None:
        """Record that connection pool was initialized."""
        ...

    def pool_initialization_failed(self, error: Exception) -> None:
        """Record that pool initialization failed."""
        ...

    def connection_acquired_from_pool(self) -> None:
        """Record that a connection was acquired from the pool."""
        ...

    def connection_returned_to_pool(self) -> None:
        """Record that a connection was returned to the pool."""
        ...

    def pool_exhausted(self) -> None:
        """Record that the connection pool was exhausted."""
        ...

    def connection_return_failed(self, error: Exception) -> None:
        """Record that returning connection to pool failed."""
        ...

    def pool_closed(self) -> None:
        """Record that the connection pool was closed."""
        ...

    def with_context(self, context: ObservationContext) -> ConnectionProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultConnectionProbe:
    """Default implementation of ConnectionProbe using structlog.

    Supports observation context for including request-scoped metadata
    with all log events.
    """

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        """Get context metadata as kwargs for logging."""
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(self, context: ObservationContext) -> DefaultConnectionProbe:
        """Create a new probe with observation context bound."""
        return DefaultConnectionProbe(logger=self._logger, context=context)

    def connection_established(self, host: str, database: str) -> None:
        """Record that a database connection was successfully established."""
        self._logger.info(
            "database_connection_established",
            host=host,
            database=database,
            **self._get_context_kwargs(),
        )

    def connection_failed(self, host: str, database: str, error: Exception) -> None:
        """Record that a database connection attempt failed."""
        self._logger.error(
            "database_connection_failed",
            host=host,
            database=database,
            error=str(error),
            **self._get_context_kwargs(),
        )

    def connection_closed(self) -> None:
        """Record that a database connection was closed."""
        self._logger.info(
            "database_connection_closed",
            **self._get_context_kwargs(),
        )

    def pool_initialized(self, min_conn: int, max_conn: int) -> None:
        """Record that connection pool was initialized."""
        self._logger.info(
            "connection_pool_initialized",
            min_connections=min_conn,
            max_connections=max_conn,
            **self._get_context_kwargs(),
        )

    def pool_initialization_failed(self, error: Exception) -> None:
        """Record that pool initialization failed."""
        self._logger.error(
            "connection_pool_initialization_failed",
            error=str(error),
            **self._get_context_kwargs(),
        )

    def connection_acquired_from_pool(self) -> None:
        """Record that a connection was acquired from the pool."""
        self._logger.debug(
            "connection_acquired_from_pool",
            **self._get_context_kwargs(),
        )

    def connection_returned_to_pool(self) -> None:
        """Record that a connection was returned to the pool."""
        self._logger.debug(
            "connection_returned_to_pool",
            **self._get_context_kwargs(),
        )

    def pool_exhausted(self) -> None:
        """Record that the connection pool was exhausted."""
        self._logger.warning(
            "connection_pool_exhausted",
            **self._get_context_kwargs(),
        )

    def connection_return_failed(self, error: Exception) -> None:
        """Record that returning connection to pool failed."""
        self._logger.error(
            "connection_return_failed",
            error=str(error),
            **self._get_context_kwargs(),
        )

    def pool_closed(self) -> None:
        """Record that the connection pool was closed."""
        self._logger.info(
            "connection_pool_closed",
            **self._get_context_kwargs(),
        )
