"""ExtractionEventHandler: processes JobPackageProduced events from the outbox.

When a JobPackageProduced event is processed, this handler runs the extraction
pipeline and emits either MutationLogProduced or ExtractionFailed to the outbox.

The extraction pipeline is the AI-based entity extraction phase of the sync
lifecycle, where the Claude Agent SDK discovers entities and relationships
from the raw data packaged by the Ingestion context.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from extraction.ports.runtime import (
    EphemeralWorkerLaunchRequest,
    IEphemeralExtractionWorkerLauncher,
    IWorkloadCredentialIssuer,
    ScopedWorkloadCredentials,
)
from extraction.ports.services import IExtractionService

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from shared_kernel.outbox.ports import IOutboxRepository


class ExtractionEventHandler:
    """Handles JobPackageProduced events by running the extraction pipeline.

    When a JobPackageProduced event is processed from the outbox, this handler:
    1. Issues short-lived scoped credentials and launches an ephemeral worker
    2. Delegates to IExtractionService.run() to extract entities and relationships
    3. On success: appends MutationLogProduced to the outbox
    4. On failure: appends ExtractionFailed to the outbox

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
        *,
        credential_issuer: IWorkloadCredentialIssuer | None = None,
        worker_launcher: IEphemeralExtractionWorkerLauncher | None = None,
    ) -> None:
        """Initialize the extraction event handler.

        Args:
            extraction_service: Service that runs the AI extraction pipeline
            outbox: Repository for writing output events (MutationLogProduced /
                ExtractionFailed)
            runtime_context_builder: Resolves runtime paths for the workload
            credential_issuer: Optional issuer for runtime-only workload credentials
            worker_launcher: Optional launcher that enforces credential scope
        """
        if (credential_issuer is None) ^ (worker_launcher is None):
            raise ValueError(
                "credential_issuer and worker_launcher must be configured together"
            )

        self._extraction_service = extraction_service
        self._outbox = outbox
        self._runtime_context_builder = runtime_context_builder
        self._credential_issuer = credential_issuer
        self._worker_launcher = worker_launcher

    def supported_event_types(self) -> frozenset[str]:
        """Return event types handled by this handler."""
        return frozenset({"JobPackageProduced"})

    @staticmethod
    def _redact_sensitive_error(message: str) -> str:
        """Redact token-like secrets from error strings before persistence."""
        patterns = (
            re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{16,}\b"),
            re.compile(
                r"(?i)\b(token|access_token|password|api[_-]?key)\b\s*[:=]\s*['\"]?[^\s,'\"]+"
            ),
        )
        redacted = message
        for pattern in patterns:
            redacted = pattern.sub("***REDACTED***", redacted)
        return redacted

    @classmethod
    def _sanitize_failure_error(
        cls,
        exc: Exception,
        *,
        workload_credentials: ScopedWorkloadCredentials | None,
    ) -> str:
        message = str(exc)
        if workload_credentials is not None and workload_credentials.token:
            message = message.replace(workload_credentials.token, "***REDACTED***")
        return cls._redact_sensitive_error(message)

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        tenant_id: str | None = None,
    ) -> None:
        """Process a JobPackageProduced event by running the extraction pipeline.

        Args:
            event_type: Must be "JobPackageProduced"
            payload: The JobPackageProduced event payload, containing:
                - sync_run_id: The sync run to update
                - data_source_id: The data source being extracted
                - knowledge_graph_id: The target knowledge graph
                - job_package_id: The JobPackage to process
            tenant_id: Tenant scope used for runtime credential issuance
        """
        if event_type != "JobPackageProduced":
            return

        sync_run_id = payload["sync_run_id"]
        data_source_id = payload["data_source_id"]
        knowledge_graph_id = payload["knowledge_graph_id"]
        job_package_id = payload["job_package_id"]
        now = datetime.now(UTC)

        workload_credentials: ScopedWorkloadCredentials | None = None
        worker_id: str | None = None

        try:
            if (
                self._credential_issuer is not None
                and self._worker_launcher is not None
            ):
                if not tenant_id:
                    raise ValueError(
                        "tenant_id is required for scoped workload credential injection"
                    )

                workload_credentials = self._credential_issuer.issue(
                    tenant_id=tenant_id,
                    knowledge_graph_id=knowledge_graph_id,
                )
                launch_result = self._worker_launcher.launch(
                    request=EphemeralWorkerLaunchRequest(
                        tenant_id=tenant_id,
                        knowledge_graph_id=knowledge_graph_id,
                        session_id=f"sync:{sync_run_id}",
                        sync_run_id=sync_run_id,
                        job_package_id=job_package_id,
                    ),
                    credentials=workload_credentials,
                )
                worker_id = launch_result.worker_id

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
                workload_credentials=workload_credentials,
            )
        except Exception as exc:
            await self._outbox.append(
                event_type="ExtractionFailed",
                payload={
                    "sync_run_id": sync_run_id,
                    "data_source_id": data_source_id,
                    "error": self._sanitize_failure_error(
                        exc,
                        workload_credentials=workload_credentials,
                    ),
                    "occurred_at": now.isoformat(),
                },
                occurred_at=now,
                aggregate_type="sync_run",
                aggregate_id=sync_run_id,
            )
            return
        finally:
            if worker_id is not None and self._worker_launcher is not None:
                try:
                    self._worker_launcher.complete_worker(worker_id)
                except Exception:
                    logger.exception(
                        "Failed to complete extraction worker cleanup",
                        extra={"worker_id": worker_id, "sync_run_id": sync_run_id},
                    )

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
