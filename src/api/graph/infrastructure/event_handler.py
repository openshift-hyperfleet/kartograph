"""GraphMutationEventHandler: processes MutationLogProduced events from the outbox.

When a MutationLogProduced event is processed, this handler applies the
mutation log to the graph database and emits either MutationsApplied or
MutationApplicationFailed to the outbox.

This handler is the Graph bounded context's entry point in the sync lifecycle.
It bridges the Extraction context (which produces MutationLogs) and the Graph
context (which applies those mutations to the Apache AGE database).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from graph.ports.mutation_log import IMutationLogApplier

if TYPE_CHECKING:
    from shared_kernel.outbox.ports import IOutboxRepository


class GraphMutationEventHandler:
    """Handles MutationLogProduced events by applying mutations to the graph.

    When a MutationLogProduced event is processed from the outbox:
    1. Delegates to IMutationLogApplier.apply_mutation_log() to apply mutations
    2. On success: appends MutationsApplied to the outbox
    3. On failure: appends MutationApplicationFailed to the outbox

    The 'mutation job record' is tracked via the sync run's status
    transitioning to 'applying' (handled by SyncLifecycleHandler).
    """

    def __init__(
        self,
        mutation_log_applier: IMutationLogApplier,
        outbox: "IOutboxRepository",
    ) -> None:
        """Initialize the graph mutation event handler.

        Args:
            mutation_log_applier: Service that applies MutationLog content
                to the graph database
            outbox: Repository for writing output events (MutationsApplied /
                MutationApplicationFailed)
        """
        self._mutation_log_applier = mutation_log_applier
        self._outbox = outbox

    def supported_event_types(self) -> frozenset[str]:
        """Return event types handled by this handler."""
        return frozenset({"MutationLogProduced"})

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Process a MutationLogProduced event by applying mutations to the graph.

        Args:
            event_type: Must be "MutationLogProduced"
            payload: The MutationLogProduced event payload, containing:
                - sync_run_id: The sync run to update
                - data_source_id: The data source that was extracted
                - knowledge_graph_id: The target knowledge graph
                - mutation_log_id: The MutationLog to apply
        """
        if event_type != "MutationLogProduced":
            return

        sync_run_id = payload["sync_run_id"]
        data_source_id = payload["data_source_id"]
        knowledge_graph_id = payload["knowledge_graph_id"]
        mutation_log_id = payload["mutation_log_id"]
        now = datetime.now(UTC)

        try:
            success = await self._mutation_log_applier.apply_mutation_log(
                mutation_log_id
            )

            if success:
                await self._outbox.append(
                    event_type="MutationsApplied",
                    payload={
                        "sync_run_id": sync_run_id,
                        "data_source_id": data_source_id,
                        "knowledge_graph_id": knowledge_graph_id,
                        "occurred_at": now.isoformat(),
                    },
                    occurred_at=now,
                    aggregate_type="sync_run",
                    aggregate_id=sync_run_id,
                )
            else:
                await self._outbox.append(
                    event_type="MutationApplicationFailed",
                    payload={
                        "sync_run_id": sync_run_id,
                        "data_source_id": data_source_id,
                        "error": "Mutation application returned failure",
                        "occurred_at": now.isoformat(),
                    },
                    occurred_at=now,
                    aggregate_type="sync_run",
                    aggregate_id=sync_run_id,
                )

        except Exception as exc:
            await self._outbox.append(
                event_type="MutationApplicationFailed",
                payload={
                    "sync_run_id": sync_run_id,
                    "data_source_id": data_source_id,
                    "error": str(exc),
                    "occurred_at": now.isoformat(),
                },
                occurred_at=now,
                aggregate_type="sync_run",
                aggregate_id=sync_run_id,
            )
