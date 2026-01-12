"""Observability protocols for Graph bounded context.

Defines protocols for domain probes that can be implemented by infrastructure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class MutationProbe(Protocol):
    """Domain probe for mutation operation observability.

    This probe captures domain-significant events related to graph
    mutation operations (CREATE, UPDATE, DELETE, DEFINE).
    """

    def mutation_applied(
        self,
        operation: str,
        entity_type: str,
        entity_id: str | None,
    ) -> None:
        """Record that a mutation was successfully applied.

        Args:
            operation: The operation type (DEFINE, CREATE, UPDATE, DELETE)
            entity_type: The entity type (node or edge)
            entity_id: The entity ID (None for DEFINE operations)
        """
        ...

    def batch_applied(
        self,
        operation: str,
        entity_type: str,
        label: str | None,
        count: int,
        duration_ms: float,
    ) -> None:
        """Record that a batch of mutations was successfully applied.

        Args:
            operation: The operation type (CREATE, UPDATE, DELETE)
            entity_type: The entity type (node or edge)
            label: The label for CREATE operations (None for UPDATE/DELETE)
            count: Number of operations in the batch
            duration_ms: Time taken to execute the batch in milliseconds
        """
        ...

    def apply_batch_completed(
        self,
        total_operations: int,
        total_batches: int,
        duration_ms: float,
        success: bool,
    ) -> None:
        """Record completion of the entire apply_batch operation.

        Args:
            total_operations: Total number of operations processed
            total_batches: Total number of batch queries executed
            duration_ms: Total time for the entire operation in milliseconds
            success: Whether the operation completed successfully
        """
        ...

    def with_context(self, context: ObservationContext) -> MutationProbe:
        """Create a new probe with observation context bound."""
        ...
