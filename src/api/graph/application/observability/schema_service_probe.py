"""Protocol for schema service observability.

Defines the interface for domain probes that capture schema/ontology
operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class SchemaServiceProbe(Protocol):
    """Domain probe for schema service operations."""

    def ontology_retrieved(
        self,
        count: int,
    ) -> None:
        """Record that the ontology was retrieved."""
        ...

    def with_context(self, context: ObservationContext) -> SchemaServiceProbe:
        """Create a new probe with observation context bound."""
        ...
