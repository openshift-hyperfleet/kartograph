"""Domain probe for sticky session runtime lifecycle.

Following Domain-Oriented Observability patterns, this probe captures
sticky-runtime start failures (container/OpenShell sandbox start, Vertex
provider bootstrap, health checks) so the raw failure detail is visible in
structured logs instead of only ever reaching the end user's browser.

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class StickySessionRuntimeProbe(Protocol):
    """Domain probe for sticky session runtime start/health operations."""

    def runtime_start_failed(
        self,
        *,
        session_id: str,
        knowledge_graph_id: str,
        mode: str,
        error: str,
    ) -> None:
        """Record that starting the sticky runtime (container/sandbox) failed."""
        ...

    def runtime_unhealthy(
        self,
        *,
        session_id: str,
        knowledge_graph_id: str,
        mode: str,
        error: str,
    ) -> None:
        """Record that the sticky runtime never became healthy in time."""
        ...

    def with_context(self, context: ObservationContext) -> StickySessionRuntimeProbe:
        """Return a new probe with additional context."""
        ...


class DefaultStickySessionRuntimeProbe:
    """Default implementation of StickySessionRuntimeProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self, exclude: set[str] | None = None) -> dict[str, str]:
        if self._context is None:
            return {}
        context_dict = self._context.as_dict()
        if exclude:
            return {k: v for k, v in context_dict.items() if k not in exclude}
        return context_dict

    def with_context(
        self, context: ObservationContext
    ) -> DefaultStickySessionRuntimeProbe:
        return DefaultStickySessionRuntimeProbe(logger=self._logger, context=context)

    def runtime_start_failed(
        self,
        *,
        session_id: str,
        knowledge_graph_id: str,
        mode: str,
        error: str,
    ) -> None:
        context_kwargs = self._get_context_kwargs(
            exclude={"session_id", "knowledge_graph_id", "mode", "error"}
        )
        self._logger.error(
            "sticky_runtime_start_failed",
            session_id=session_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            error=error,
            **context_kwargs,
        )

    def runtime_unhealthy(
        self,
        *,
        session_id: str,
        knowledge_graph_id: str,
        mode: str,
        error: str,
    ) -> None:
        context_kwargs = self._get_context_kwargs(
            exclude={"session_id", "knowledge_graph_id", "mode", "error"}
        )
        self._logger.error(
            "sticky_runtime_unhealthy",
            session_id=session_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            error=error,
            **context_kwargs,
        )
