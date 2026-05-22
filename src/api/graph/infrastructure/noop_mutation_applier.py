"""No-op mutation applier for schema-only DEFINE batches."""

from __future__ import annotations

from graph.domain.value_objects import MutationOperation, MutationResult


class NoOpMutationApplier:
    """Accept mutation batches without touching the graph database."""

    def apply_batch(self, operations: list[MutationOperation]) -> MutationResult:
        """Report success for schema-only batches."""
        _ = operations
        return MutationResult(success=True, operations_applied=0)
