"""IngestionEventHandler: processes SyncStarted events from the outbox.

When a SyncStarted event is processed, this handler runs the ingestion
pipeline and emits either JobPackageProduced or IngestionFailed to the outbox.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ingestion.ports.services import IIngestionService

if TYPE_CHECKING:
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
        ingestion_service: IIngestionService,
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

    @staticmethod
    def _redact_sensitive_error(message: str) -> str:
        """Redact token-like secrets from error strings before persistence."""
        patterns = (
            # GitHub PAT prefixes
            re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
            # Generic bearer tokens
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{16,}\b"),
            # Common key/value credential leaks
            re.compile(
                r"(?i)\b(token|access_token|password|api[_-]?key)\b\s*[:=]\s*['\"]?[^\s,'\"]+"
            ),
        )
        redacted = message
        for pattern in patterns:
            redacted = pattern.sub("***REDACTED***", redacted)
        return redacted

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
        runtime_credentials: dict[str, str] | None = None,
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

        pipeline_mode = payload.get("pipeline_mode", "full")
        ingest_only = pipeline_mode == "ingest_only"

        if payload.get("no_changes_detected") is True:
            if ingest_only:
                await self._outbox.append(
                    event_type="IngestionPrepared",
                    payload={
                        "sync_run_id": sync_run_id,
                        "data_source_id": data_source_id,
                        "knowledge_graph_id": knowledge_graph_id,
                        "no_changes_detected": True,
                        "occurred_at": now.isoformat(),
                    },
                    occurred_at=now,
                    aggregate_type="sync_run",
                    aggregate_id=sync_run_id,
                )
            else:
                await self._outbox.append(
                    event_type="MutationsApplied",
                    payload={
                        "sync_run_id": sync_run_id,
                        "data_source_id": data_source_id,
                        "knowledge_graph_id": knowledge_graph_id,
                        "no_changes_detected": True,
                        "occurred_at": now.isoformat(),
                    },
                    occurred_at=now,
                    aggregate_type="sync_run",
                    aggregate_id=sync_run_id,
                )
            return

        try:
            job_package_id = await self._ingestion_service.run(
                sync_run_id=sync_run_id,
                data_source_id=data_source_id,
                knowledge_graph_id=knowledge_graph_id,
                adapter_type=payload["adapter_type"],
                connection_config=payload.get("connection_config", {}),
                credentials_path=payload.get("credentials_path"),
                tenant_id=payload.get("tenant_id"),
                credentials=runtime_credentials or payload.get("credentials"),
                baseline_commit=payload.get("baseline_commit"),
            )
        except asyncio.CancelledError:
            # Propagate task cancellation so the event loop can shut down
            # gracefully.  CancelledError must never be swallowed here.
            raise
        except Exception as exc:
            await self._outbox.append(
                event_type="IngestionFailed",
                payload={
                    "sync_run_id": sync_run_id,
                    "data_source_id": data_source_id,
                    "error": self._redact_sensitive_error(str(exc)),
                    "occurred_at": now.isoformat(),
                },
                occurred_at=now,
                aggregate_type="sync_run",
                aggregate_id=sync_run_id,
            )
            return

        # Ingestion succeeded — append success event outside the try block so
        # that an outbox write failure is not misclassified as IngestionFailed.
        if ingest_only:
            await self._outbox.append(
                event_type="IngestionPrepared",
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
        else:
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
