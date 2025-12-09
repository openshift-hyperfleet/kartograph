"""Domain probes for Graph bounded context observability.

These probes capture domain-significant events related to graph operations,
following the Domain Oriented Observability pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from infrastructure.observability.context import ObservationContext


class GraphClientProbe(Protocol):
    """Domain probe for graph client observability.

    This probe captures domain-significant events related to graph
    database operations without exposing logging implementation details.
    """

    def connected_to_graph(self, graph_name: str) -> None:
        """Record successful connection to a graph."""
        ...

    def graph_created(self, graph_name: str) -> None:
        """Record that a new graph was created."""
        ...

    def connection_verification_failed(self, error: Exception) -> None:
        """Record that connection verification failed."""
        ...

    def query_failed(self, query: str, error: Exception) -> None:
        """Record that a Cypher query execution failed."""
        ...

    def with_context(self, context: ObservationContext) -> GraphClientProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultGraphClientProbe:
    """Default implementation of GraphClientProbe using structlog.

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

    def with_context(self, context: ObservationContext) -> DefaultGraphClientProbe:
        """Create a new probe with observation context bound."""
        return DefaultGraphClientProbe(logger=self._logger, context=context)

    def connected_to_graph(self, graph_name: str) -> None:
        """Record successful connection to a graph."""
        self._logger.info(
            "graph_connected",
            graph_name=graph_name,
            **self._get_context_kwargs(),
        )

    def graph_created(self, graph_name: str) -> None:
        """Record that a new graph was created."""
        self._logger.info(
            "graph_created",
            graph_name=graph_name,
            **self._get_context_kwargs(),
        )

    def connection_verification_failed(self, error: Exception) -> None:
        """Record that connection verification failed."""
        self._logger.warning(
            "graph_connection_verification_failed",
            error=str(error),
            **self._get_context_kwargs(),
        )

    def query_failed(self, query: str, error: Exception) -> None:
        """Record that a Cypher query execution failed."""
        self._logger.error(
            "graph_query_failed",
            query=query,
            error=str(error),
            **self._get_context_kwargs(),
        )
