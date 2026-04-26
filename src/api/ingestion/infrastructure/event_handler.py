"""IngestionEventHandler: processes SyncStarted events from the outbox.

When a SyncStarted event is processed, this handler runs the ingestion
pipeline and emits either JobPackageProduced or IngestionFailed to the outbox.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ingestion.application.services.ingestion_service import IngestionService
    from shared_kernel.outbox.ports import IOutboxRepository


class IngestionEventHandler:
    """Handles SyncStarted events by running the ingestion pipeline.

    When a SyncStarted event is processed from the outbox, this handler:
    1. Delegates to IngestionService.run() to extract and package data
    2. On success: appends JobPackageProduced to the outbox
    3. On failure: appends IngestionFailed to the outbox

    The handler is designed to be idempotent — if the pipeline succeeds
    but the outbox write fails, re-delivery will attempt the ingestion again.
    Adapters should handle this gracefully (e.g., by returning the same
    data for unchanged items).
    """

    def __init__(
        self,
        ingestion_service: "IngestionService",
        outbox: "IOutboxRepository",
    ) -> None:
        """Initialize the ingestion event handler.

        Args:
            ingestion_service: Service that runs the extract → package pipeline
            outbox: Repository for writing output events (JobPackageProduced /
                IngestionFailed)
        """
        self._ingestion_service = ingestion_service
        self._outbox = outbox

    def supported_event_types(self) -> frozenset[str]:
        """Return event types handled by this handler."""
        return frozenset({"SyncStarted"})

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Process a SyncStarted event by running the ingestion pipeline.

        Args:
            event_type: Must be "SyncStarted"
            payload: The SyncStarted event payload, containing:
                - sync_run_id: The sync run to update
                - data_source_id: The data source to ingest
                - knowledge_graph_id: The target knowledge graph
                - adapter_type: Which adapter to use
                - connection_config: Adapter configuration
                - credentials_path: Optional vault path for credentials
        """
        if event_type != "SyncStarted":
            return

        sync_run_id = payload["sync_run_id"]
        data_source_id = payload["data_source_id"]
        knowledge_graph_id = payload["knowledge_graph_id"]
        now = datetime.now(UTC)

        try:
            job_package_id = await self._ingestion_service.run(
                sync_run_id=sync_run_id,
                data_source_id=data_source_id,
                knowledge_graph_id=knowledge_graph_id,
                adapter_type=payload["adapter_type"],
                connection_config=payload.get("connection_config", {}),
                credentials_path=payload.get("credentials_path"),
            )

            await self._outbox.append(
                event_type="JobPackageProduced",
                payload={
                    "sync_run_id": sync_run_id,
                    "data_source_id": data_source_id,
                    "knowledge_graph_id": knowledge_graph_id,
                    "job_package_id": str(job_package_id),
                    "occurred_at": now.isoformat(),
                },
                occurred_at=now,
                aggregate_type="sync_run",
                aggregate_id=sync_run_id,
            )

        except Exception as exc:
            await self._outbox.append(
                event_type="IngestionFailed",
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
