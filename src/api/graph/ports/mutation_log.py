"""Port protocols for mutation log application in the Graph bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class MutationLogApplyResult:
    """Result metadata produced when applying a mutation log."""

    success: bool
    operation_counts: dict[str, int] = field(default_factory=dict)
    token_usage_total: int | None = None
    cost_total_usd: float | None = None


class IMutationLogApplier(Protocol):
    """Protocol for applying a MutationLog to the graph database.

    Implementations retrieve the MutationLog content by ID, parse the JSONL,
    and apply all operations to the Apache AGE database atomically.

    This port decouples the GraphMutationEventHandler from the concrete
    infrastructure (AGE connection pools, bulk loading strategies, etc.).
    """

    async def apply_mutation_log(self, mutation_log_id: str) -> MutationLogApplyResult:
        """Apply all mutations from a MutationLog to the graph database.

        Args:
            mutation_log_id: Identifier of the MutationLog to apply.
                The implementation is responsible for retrieving the
                log content from storage (filesystem, object store, etc.).

        Returns:
            MutationLogApplyResult with success flag and finalized run metrics.

        Raises:
            Exception: Any exception signals a failure; callers should
                catch and emit MutationApplicationFailed to the outbox.
        """
        ...
