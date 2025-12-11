"""Domain probes for Graph application layer.

These probes capture application-level domain events, providing
observability at the use-case level rather than infrastructure level.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from infrastructure.observability.context import ObservationContext


class GraphServiceProbe(Protocol):
    """Domain probe for graph service operations."""

    def nodes_queried(
        self,
        path: str,
        node_count: int,
        edge_count: int,
    ) -> None:
        """Record that nodes were queried by path."""
        ...

    def slug_searched(
        self,
        slug: str,
        node_type: str | None,
        result_count: int,
    ) -> None:
        """Record that a slug search was performed."""
        ...

    def raw_query_executed(
        self,
        query: str,
        result_count: int,
    ) -> None:
        """Record that a raw query was executed."""
        ...

    def mutations_applied(
        self,
        operations_applied: int,
        success: bool,
    ) -> None:
        """Record that a batch of mutations was applied."""
        ...

    def with_context(self, context: ObservationContext) -> GraphServiceProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultGraphServiceProbe:
    """Default implementation of GraphServiceProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(self, context: ObservationContext) -> DefaultGraphServiceProbe:
        return DefaultGraphServiceProbe(logger=self._logger, context=context)

    def nodes_queried(
        self,
        path: str,
        node_count: int,
        edge_count: int,
    ) -> None:
        self._logger.info(
            "graph_nodes_queried",
            path=path,
            node_count=node_count,
            edge_count=edge_count,
            **self._get_context_kwargs(),
        )

    def slug_searched(
        self,
        slug: str,
        node_type: str | None,
        result_count: int,
    ) -> None:
        self._logger.info(
            "graph_slug_searched",
            slug=slug,
            node_type=node_type,
            result_count=result_count,
            **self._get_context_kwargs(),
        )

    def raw_query_executed(
        self,
        query: str,
        result_count: int,
    ) -> None:
        self._logger.info(
            "graph_raw_query_executed",
            query=query,
            result_count=result_count,
            **self._get_context_kwargs(),
        )

    def mutations_applied(
        self,
        operations_applied: int,
        success: bool,
    ) -> None:
        level = "info" if success else "error"
        getattr(self._logger, level)(
            "graph_mutations_applied",
            operations_applied=operations_applied,
            success=success,
            **self._get_context_kwargs(),
        )
