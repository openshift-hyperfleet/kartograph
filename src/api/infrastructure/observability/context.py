"""Observation context for domain-oriented observability.

Observation contexts collect and manage contextual metadata for instrumentation,
following the Domain Oriented Observability pattern.

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ObservationContext:
    """Immutable context containing metadata for observability.

    Captures request-scoped and domain-relevant metadata that should be
    included with all instrumentation events. This enables correlation
    of events across services and provides business context for debugging.

    Attributes:
        request_id: Unique identifier for the current request/operation.
        user_id: Identifier of the user performing the operation (if applicable).
        tenant_id: Multi-tenant identifier (if applicable).
        graph_name: Name of the graph being operated on (if applicable).
        extra: Additional contextual metadata.

    Example:
        context = ObservationContext(
            request_id="req-123",
            user_id="user-456",
            graph_name="my_graph",
        )
        probe = DefaultConnectionProbe().with_context(context)
    """

    request_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    graph_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Convert context to a dictionary for logging.

        Only includes non-None values to keep logs clean.
        """
        result: dict[str, Any] = {}
        if self.request_id is not None:
            result["request_id"] = self.request_id
        if self.user_id is not None:
            result["user_id"] = self.user_id
        if self.tenant_id is not None:
            result["tenant_id"] = self.tenant_id
        if self.graph_name is not None:
            result["graph_name"] = self.graph_name
        result.update(self.extra)
        return result

    def with_graph(self, graph_name: str) -> ObservationContext:
        """Create a new context with the graph name set."""
        return ObservationContext(
            request_id=self.request_id,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            graph_name=graph_name,
            extra=self.extra,
        )

    def with_extra(self, **kwargs: Any) -> ObservationContext:
        """Create a new context with additional metadata."""
        new_extra = {**self.extra, **kwargs}
        return ObservationContext(
            request_id=self.request_id,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            graph_name=self.graph_name,
            extra=new_extra,
        )
