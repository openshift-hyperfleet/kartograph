"""Port protocols for mutation log application in the Graph bounded context."""

from __future__ import annotations

from typing import Protocol


class IMutationLogApplier(Protocol):
    """Protocol for applying a MutationLog to the graph database.

    Implementations retrieve the MutationLog content by ID, parse the JSONL,
    and apply all operations to the Apache AGE database atomically.

    This port decouples the GraphMutationEventHandler from the concrete
    infrastructure (AGE connection pools, bulk loading strategies, etc.).
    """

    async def apply_mutation_log(self, mutation_log_id: str) -> bool:
        """Apply all mutations from a MutationLog to the graph database.

        Args:
            mutation_log_id: Identifier of the MutationLog to apply.
                The implementation is responsible for retrieving the
                log content from storage (filesystem, object store, etc.).

        Returns:
            True if all mutations were applied successfully.

        Raises:
            Exception: Any exception signals a failure; callers should
                catch and emit MutationApplicationFailed to the outbox.
        """
        ...
