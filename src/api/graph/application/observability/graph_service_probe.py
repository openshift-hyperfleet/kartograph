"""Protocol for graph service observability.

Defines the interface for domain probes that capture application-level
domain events for graph service operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


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
