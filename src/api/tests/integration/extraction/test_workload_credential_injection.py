"""Integration tests for extraction workload credential injection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from extraction.infrastructure.event_handler import ExtractionEventHandler
from extraction.infrastructure.workload_runtime import (
    InMemoryEphemeralExtractionWorkerLauncher,
    ScopedWorkloadCredentialIssuer,
)
from extraction.ports.runtime import ScopedWorkloadCredentials
from extraction.ports.services import ExtractionRuntimeContext

pytestmark = pytest.mark.integration


class _RecordingOutbox:
    def __init__(self) -> None:
        self.appended: list[dict[str, Any]] = []

    async def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
        aggregate_type: str,
        aggregate_id: str,
    ) -> None:
        self.appended.append(
            {
                "event_type": event_type,
                "payload": payload,
                "occurred_at": occurred_at,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
            }
        )

    async def fetch_unprocessed(self, limit: int = 100) -> list[Any]:
        return []

    async def mark_processed(self, entry_id: UUID) -> None:
        pass


class _RecordingExtractionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(
        self,
        sync_run_id: str,
        data_source_id: str,
        knowledge_graph_id: str,
        job_package_id: str,
        runtime_context: ExtractionRuntimeContext,
        workload_credentials: ScopedWorkloadCredentials | None = None,
    ) -> str:
        self.calls.append(
            {
                "sync_run_id": sync_run_id,
                "workload_credentials": workload_credentials,
            }
        )
        return "mutation-log-integration"


class _StaticRuntimeContextBuilder:
    def build(self, *, sync_run_id: str, job_package_id: str) -> ExtractionRuntimeContext:
        return ExtractionRuntimeContext(
            ingestion_context_dir="/tmp/ingestion-context",
            repository_files_dir="/tmp/repository-files",
            job_package_archive="/tmp/job-package.zip",
        )


def _payload(*, tenant_id: str = "tenant-integration") -> dict[str, Any]:
    return {
        "sync_run_id": "sync-integration-1",
        "data_source_id": "ds-integration-1",
        "knowledge_graph_id": "kg-integration-1",
        "job_package_id": "pkg-integration-1",
        "tenant_id": tenant_id,
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def _handler(
    *,
    service: _RecordingExtractionService | None = None,
    launcher: InMemoryEphemeralExtractionWorkerLauncher | None = None,
) -> tuple[ExtractionEventHandler, _RecordingOutbox, _RecordingExtractionService, InMemoryEphemeralExtractionWorkerLauncher]:
    outbox = _RecordingOutbox()
    extraction_service = service or _RecordingExtractionService()
    worker_launcher = launcher or InMemoryEphemeralExtractionWorkerLauncher()
    handler = ExtractionEventHandler(
        extraction_service=extraction_service,
        outbox=outbox,
        runtime_context_builder=_StaticRuntimeContextBuilder(),
        credential_issuer=ScopedWorkloadCredentialIssuer(default_ttl=timedelta(minutes=10)),
        worker_launcher=worker_launcher,
    )
    return handler, outbox, extraction_service, worker_launcher


@pytest.mark.asyncio
async def test_scoped_credentials_are_injected_at_runtime_only() -> None:
    handler, outbox, service, launcher = _handler()

    await handler.handle("JobPackageProduced", _payload(), tenant_id="tenant-integration")

    assert len(service.calls) == 1
    credentials = service.calls[0]["workload_credentials"]
    assert credentials is not None
    assert credentials.scopes == (
        "tenant:tenant-integration",
        "knowledge_graph:kg-integration-1",
        "workload:extraction",
    )
    assert launcher.active_worker_count == 0
    assert len(outbox.appended) == 1
    success = outbox.appended[0]
    assert success["event_type"] == "MutationLogProduced"
    assert "token" not in success["payload"]
    assert credentials.token not in str(success["payload"])


@pytest.mark.asyncio
async def test_rejects_credentials_with_insufficient_scope() -> None:
    outbox = _RecordingOutbox()
    service = _RecordingExtractionService()
    launcher = InMemoryEphemeralExtractionWorkerLauncher()

    class _WrongScopeIssuer:
        def issue(
            self, *, tenant_id: str, knowledge_graph_id: str
        ) -> ScopedWorkloadCredentials:
            return ScopedWorkloadCredentials(
                token="wrong-scope-token",
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
                scopes=(
                    "tenant:tenant-other",
                    f"knowledge_graph:{knowledge_graph_id}",
                    "workload:extraction",
                ),
            )

    handler = ExtractionEventHandler(
        extraction_service=service,
        outbox=outbox,
        runtime_context_builder=_StaticRuntimeContextBuilder(),
        credential_issuer=_WrongScopeIssuer(),
        worker_launcher=launcher,
    )

    await handler.handle(
        "JobPackageProduced",
        _payload(),
        tenant_id="tenant-integration",
    )

    assert service.calls == []
    assert len(outbox.appended) == 1
    failure = outbox.appended[0]
    assert failure["event_type"] == "ExtractionFailed"
    assert "scope" in failure["payload"]["error"].lower()
    assert "wrong-scope-token" not in failure["payload"]["error"]


@pytest.mark.asyncio
async def test_rejects_expired_credentials() -> None:
    outbox = _RecordingOutbox()
    service = _RecordingExtractionService()
    launcher = InMemoryEphemeralExtractionWorkerLauncher()

    class _ExpiredIssuer:
        def issue(
            self, *, tenant_id: str, knowledge_graph_id: str
        ) -> ScopedWorkloadCredentials:
            return ScopedWorkloadCredentials(
                token="expired-token-value",
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
                scopes=(
                    f"tenant:{tenant_id}",
                    f"knowledge_graph:{knowledge_graph_id}",
                    "workload:extraction",
                ),
            )

    handler = ExtractionEventHandler(
        extraction_service=service,
        outbox=outbox,
        runtime_context_builder=_StaticRuntimeContextBuilder(),
        credential_issuer=_ExpiredIssuer(),
        worker_launcher=launcher,
    )

    await handler.handle(
        "JobPackageProduced",
        _payload(),
        tenant_id="tenant-integration",
    )

    assert service.calls == []
    assert len(outbox.appended) == 1
    failure = outbox.appended[0]
    assert failure["event_type"] == "ExtractionFailed"
    assert "expired" in failure["payload"]["error"].lower()
    assert "expired-token-value" not in failure["payload"]["error"]
