"""Default implementation of graph service probe.

Provides a structlog-based implementation of the GraphServiceProbe protocol
for observability at the use-case level.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from graph.application.observability.graph_service_probe import GraphServiceProbe

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class DefaultGraphServiceProbe(GraphServiceProbe):
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
