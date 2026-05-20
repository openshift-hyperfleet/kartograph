"""ExtractionEventHandler: processes JobPackageProduced events from the outbox.

When a JobPackageProduced event is processed, this handler runs the extraction
pipeline and emits either MutationLogProduced or ExtractionFailed to the outbox.

The extraction pipeline is the AI-based entity extraction phase of the sync
lifecycle, where the Claude Agent SDK discovers entities and relationships
from the raw data packaged by the Ingestion context.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from extraction.ports.services import IExtractionService

if TYPE_CHECKING:
    from shared_kernel.outbox.ports import IOutboxRepository


class ExtractionEventHandler:
    """Handles JobPackageProduced events by running the extraction pipeline.

    When a JobPackageProduced event is processed from the outbox, this handler:
    1. Delegates to IExtractionService.run() to extract entities and relationships
    2. On success: appends MutationLogProduced to the outbox
    3. On failure: appends ExtractionFailed to the outbox

    This handler is the entry point for the Extraction bounded context in the
    sync lifecycle. It creates the linkage between the Ingestion context
    (which produces JobPackages) and the Extraction context (which produces
    MutationLogs for the Graph context to apply).

    The 'extraction job record' is tracked via the sync run's status
    transitioning to 'ai_extracting' (handled by SyncLifecycleHandler).
    """

    def __init__(
        self,
        extraction_service: IExtractionService,
        outbox: "IOutboxRepository",
        runtime_context_builder: Any,
    ) -> None:
        """Initialize the extraction event handler.

        Args:
            extraction_service: Service that runs the AI extraction pipeline
            outbox: Repository for writing output events (MutationLogProduced /
                ExtractionFailed)
        """
        self._extraction_service = extraction_service
        self._outbox = outbox
        self._runtime_context_builder = runtime_context_builder

    def supported_event_types(self) -> frozenset[str]:
        """Return event types handled by this handler."""
        return frozenset({"JobPackageProduced"})

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Process a JobPackageProduced event by running the extraction pipeline.

        Args:
            event_type: Must be "JobPackageProduced"
            payload: The JobPackageProduced event payload, containing:
                - sync_run_id: The sync run to update
                - data_source_id: The data source being extracted
                - knowledge_graph_id: The target knowledge graph
                - job_package_id: The JobPackage to process
        """
        if event_type != "JobPackageProduced":
            return

        sync_run_id = payload["sync_run_id"]
        data_source_id = payload["data_source_id"]
        knowledge_graph_id = payload["knowledge_graph_id"]
        job_package_id = payload["job_package_id"]
        now = datetime.now(UTC)

        try:
            runtime_context = self._runtime_context_builder.build(
                sync_run_id=sync_run_id,
                job_package_id=job_package_id,
            )
            mutation_log_id = await self._extraction_service.run(
                sync_run_id=sync_run_id,
                data_source_id=data_source_id,
                knowledge_graph_id=knowledge_graph_id,
                job_package_id=job_package_id,
                runtime_context=runtime_context,
            )
        except Exception as exc:
            await self._outbox.append(
                event_type="ExtractionFailed",
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
            return

        # Extraction succeeded — append success event outside the try block so
        # that an outbox write failure here is not mistaken for an extraction
        # failure.  If MutationLogProduced cannot be written, the exception
        # propagates to the outbox worker for a safe retry.
        await self._outbox.append(
            event_type="MutationLogProduced",
            payload={
                "sync_run_id": sync_run_id,
                "data_source_id": data_source_id,
                "knowledge_graph_id": knowledge_graph_id,
                "mutation_log_id": mutation_log_id,
                "occurred_at": now.isoformat(),
            },
            occurred_at=now,
            aggregate_type="sync_run",
            aggregate_id=sync_run_id,
        )
