"""Domain probes for infrastructure observability.

Domain probes provide a high-level instrumentation API oriented around
domain semantics, keeping infrastructure code clean and testable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

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

    def _get_context_kwargs(self) -> dict[str, str | None]:
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
