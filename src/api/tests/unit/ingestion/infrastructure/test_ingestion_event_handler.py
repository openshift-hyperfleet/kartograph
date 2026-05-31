"""Unit tests for IngestionEventHandler.

Tests that SyncStarted events trigger the ingestion pipeline
and result in JobPackageProduced or IngestionFailed being written to outbox.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from ingestion.infrastructure.event_handler import IngestionEventHandler
from ingestion.application.value_objects import IngestionRunResult
from shared_kernel.job_package.value_objects import (
    JobPackageId,
)


class _FakeOutboxRepository:
    """Fake outbox repository that captures appended events."""

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


class _FakeIngestionService:
    """Fake ingestion service that returns a fixed package ID or raises."""

    def __init__(self, fail: bool = False, error: str = "adapter failed") -> None:
        self._fail = fail
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def run(
        self,
        sync_run_id: str,
        data_source_id: str,
        knowledge_graph_id: str,
        adapter_type: str,
        connection_config: dict[str, str],
        credentials_path: str | None,
        tenant_id: str | None = None,
        credentials: dict[str, str] | None = None,
        baseline_commit: str | None = None,
    ) -> IngestionRunResult:
        self.calls.append(
            {
                "sync_run_id": sync_run_id,
                "data_source_id": data_source_id,
                "knowledge_graph_id": knowledge_graph_id,
                "adapter_type": adapter_type,
                "credentials": credentials,
                "baseline_commit": baseline_commit,
            }
        )
        if self._fail:
            raise RuntimeError(self._error)
        return IngestionRunResult(
            job_package_id=JobPackageId(value="01HRZZZZZZZZZZZZZZZZZZZZZ0"),
            entry_count=42,
            branch_file_count=99,
            prepared_commit_sha="abc123def456",
        )


@pytest.fixture
def outbox() -> _FakeOutboxRepository:
    return _FakeOutboxRepository()


@pytest.fixture
def ingestion_service() -> _FakeIngestionService:
    return _FakeIngestionService()


@pytest.fixture
def failing_service() -> _FakeIngestionService:
    return _FakeIngestionService(fail=True, error="credentials expired")


@pytest.fixture
def handler(
    ingestion_service: _FakeIngestionService,
    outbox: _FakeOutboxRepository,
) -> IngestionEventHandler:
    return IngestionEventHandler(
        ingestion_service=ingestion_service,
        outbox=outbox,
    )


def _sync_started_payload(
    sync_run_id: str = "run-001",
    adapter_type: str = "github",
) -> dict[str, Any]:
    return {
        "sync_run_id": sync_run_id,
        "data_source_id": "ds-001",
        "knowledge_graph_id": "kg-001",
        "tenant_id": "tenant-001",
        "adapter_type": adapter_type,
        "connection_config": {"repo": "org/repo"},
        "credentials_path": None,
        "occurred_at": datetime.now(UTC).isoformat(),
        "requested_by": "user-001",
    }


class TestIngestionEventHandlerSupportedEvents:
    """Tests for supported_event_types()."""

    def test_handles_sync_started(self, handler: IngestionEventHandler):
        """Handler should declare support for SyncStarted."""
        assert "SyncStarted" in handler.supported_event_types()


@pytest.mark.asyncio
class TestIngestionEventHandlerSuccess:
    """Tests for successful ingestion via SyncStarted event."""

    async def test_runs_ingestion_on_sync_started(
        self,
        handler: IngestionEventHandler,
        ingestion_service: _FakeIngestionService,
    ):
        """handle('SyncStarted', ...) should invoke the ingestion service."""
        payload = _sync_started_payload()
        await handler.handle("SyncStarted", payload)

        assert len(ingestion_service.calls) == 1
        call = ingestion_service.calls[0]
        assert call["sync_run_id"] == "run-001"
        assert call["adapter_type"] == "github"

    async def test_passes_baseline_and_credentials_through_payload(
        self,
        handler: IngestionEventHandler,
        ingestion_service: _FakeIngestionService,
    ):
        """SyncStarted payload baseline/credentials should pass to service.run()."""
        payload = _sync_started_payload()
        payload["baseline_commit"] = "abc123"
        payload["credentials"] = {"token": "secret"}

        await handler.handle("SyncStarted", payload)

        call = ingestion_service.calls[0]
        assert call["baseline_commit"] == "abc123"
        assert call["credentials"] == {"token": "secret"}

    async def test_prefers_runtime_credentials_over_payload_credentials(
        self,
        handler: IngestionEventHandler,
        ingestion_service: _FakeIngestionService,
    ):
        """Runtime credentials override payload credentials to avoid payload leakage."""
        payload = _sync_started_payload()
        payload["credentials"] = {"token": "payload-token"}

        await handler.handle(
            "SyncStarted",
            payload,
            runtime_credentials={"token": "runtime-token"},
        )

        call = ingestion_service.calls[0]
        assert call["credentials"] == {"token": "runtime-token"}

    async def test_emits_job_package_produced_on_success(
        self,
        handler: IngestionEventHandler,
        outbox: _FakeOutboxRepository,
    ):
        """Successful ingestion should append JobPackageProduced to outbox."""
        payload = _sync_started_payload(sync_run_id="run-001")
        await handler.handle("SyncStarted", payload)

        assert len(outbox.appended) == 1
        event = outbox.appended[0]
        assert event["event_type"] == "JobPackageProduced"
        assert event["payload"]["sync_run_id"] == "run-001"
        assert event["payload"]["data_source_id"] == "ds-001"
        assert event["payload"]["knowledge_graph_id"] == "kg-001"
        assert "job_package_id" in event["payload"]

    async def test_job_package_produced_aggregate_type(
        self,
        handler: IngestionEventHandler,
        outbox: _FakeOutboxRepository,
    ):
        """JobPackageProduced should have aggregate_type='sync_run'."""
        await handler.handle("SyncStarted", _sync_started_payload())

        event = outbox.appended[0]
        assert event["aggregate_type"] == "sync_run"
        assert event["aggregate_id"] == "run-001"

    async def test_short_circuits_when_no_changes_detected(
        self,
        handler: IngestionEventHandler,
        ingestion_service: _FakeIngestionService,
        outbox: _FakeOutboxRepository,
    ):
        """When no_changes_detected is true, heavy ingestion is skipped."""
        payload = _sync_started_payload(sync_run_id="run-004")
        payload["no_changes_detected"] = True
        payload["tracked_branch_head_commit"] = "abc123"
        payload["baseline_commit"] = "abc123"

        await handler.handle("SyncStarted", payload)

        assert ingestion_service.calls == []
        assert len(outbox.appended) == 1
        event = outbox.appended[0]
        assert event["event_type"] == "MutationsApplied"
        assert event["payload"]["sync_run_id"] == "run-004"
        assert event["payload"]["no_changes_detected"] is True

    async def test_emits_ingestion_prepared_when_ingest_only(
        self,
        handler: IngestionEventHandler,
        outbox: _FakeOutboxRepository,
    ):
        """ingest_only mode should stop after ingestion without JobPackageProduced."""
        payload = _sync_started_payload(sync_run_id="run-ingest")
        payload["pipeline_mode"] = "ingest_only"
        await handler.handle("SyncStarted", payload)

        assert len(outbox.appended) == 1
        event = outbox.appended[0]
        assert event["event_type"] == "IngestionPrepared"
        assert event["payload"]["job_package_id"] is not None
        assert event["payload"]["prepared_commit_sha"] == "abc123def456"
        assert event["payload"]["prepared_file_count"] == 99

    async def test_no_changes_ingest_only_emits_ingestion_prepared(
        self,
        handler: IngestionEventHandler,
        ingestion_service: _FakeIngestionService,
        outbox: _FakeOutboxRepository,
    ):
        """ingest_only with no_changes_detected should not emit MutationsApplied."""
        payload = _sync_started_payload(sync_run_id="run-nc-ingest")
        payload["pipeline_mode"] = "ingest_only"
        payload["no_changes_detected"] = True

        await handler.handle("SyncStarted", payload)

        assert ingestion_service.calls == []
        assert outbox.appended[0]["event_type"] == "IngestionPrepared"


@pytest.mark.asyncio
class TestIngestionEventHandlerFailure:
    """Tests for failed ingestion via SyncStarted event."""

    async def test_emits_ingestion_failed_on_adapter_error(
        self,
        failing_service: _FakeIngestionService,
        outbox: _FakeOutboxRepository,
    ):
        """Adapter failure should append IngestionFailed to outbox."""
        handler = IngestionEventHandler(
            ingestion_service=failing_service,
            outbox=outbox,
        )
        payload = _sync_started_payload(sync_run_id="run-002")
        await handler.handle("SyncStarted", payload)

        assert len(outbox.appended) == 1
        event = outbox.appended[0]
        assert event["event_type"] == "IngestionFailed"
        assert event["payload"]["sync_run_id"] == "run-002"
        assert event["payload"]["data_source_id"] == "ds-001"
        assert "credentials expired" in event["payload"]["error"]

    async def test_redacts_secret_material_from_failure_payload(
        self,
        outbox: _FakeOutboxRepository,
    ):
        """Failure payload must redact token-shaped credential values."""

        class _LeakyService(_FakeIngestionService):
            async def run(  # type: ignore[override]
                self,
                sync_run_id: str,
                data_source_id: str,
                knowledge_graph_id: str,
                adapter_type: str,
                connection_config: dict[str, str],
                credentials_path: str | None,
                tenant_id: str | None = None,
                credentials: dict[str, str] | None = None,
                baseline_commit: str | None = None,
            ) -> JobPackageId:
                raise RuntimeError(
                    "github auth failed for token ghp_1234567890abcdef1234567890abcdef1234"
                )

        handler = IngestionEventHandler(
            ingestion_service=_LeakyService(),
            outbox=outbox,
        )
        payload = _sync_started_payload(sync_run_id="run-redact")
        await handler.handle(
            "SyncStarted",
            payload,
            runtime_credentials={
                "token": "ghp_1234567890abcdef1234567890abcdef1234"
            },
        )

        event = outbox.appended[0]
        assert event["event_type"] == "IngestionFailed"
        assert "ghp_1234567890abcdef1234567890abcdef1234" not in event["payload"][
            "error"
        ]
        assert "***REDACTED***" in event["payload"]["error"]

    async def test_ingestion_failed_aggregate_type(
        self,
        failing_service: _FakeIngestionService,
        outbox: _FakeOutboxRepository,
    ):
        """IngestionFailed should have aggregate_type='sync_run'."""
        handler = IngestionEventHandler(
            ingestion_service=failing_service,
            outbox=outbox,
        )
        await handler.handle(
            "SyncStarted", _sync_started_payload(sync_run_id="run-003")
        )

        event = outbox.appended[0]
        assert event["aggregate_type"] == "sync_run"
        assert event["aggregate_id"] == "run-003"


class _FailingOutboxRepository(_FakeOutboxRepository):
    """Outbox repository that raises on the first write (simulates outbox failure)."""

    def __init__(self) -> None:
        super().__init__()
        self._call_count = 0

    async def append(  # type: ignore[override]
        self,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
        aggregate_type: str,
        aggregate_id: str,
    ) -> None:
        self._call_count += 1
        if self._call_count == 1:
            raise RuntimeError("outbox write failed")
        await super().append(
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
        )


@pytest.mark.asyncio
class TestIngestionEventHandlerOutboxIsolation:
    """Tests that success-path outbox failures are not misclassified as IngestionFailed.

    Regression guard for the 'success-path outbox wrap' bug where placing
    self._outbox.append(JobPackageProduced) inside the try block caused an
    outbox write failure to emit IngestionFailed even though ingestion succeeded.
    """

    async def test_outbox_failure_after_successful_ingestion_propagates(
        self,
        ingestion_service: _FakeIngestionService,
    ):
        """If ingestion succeeds but appending JobPackageProduced fails,
        the exception must propagate — NOT emit IngestionFailed."""
        failing_outbox = _FailingOutboxRepository()
        handler = IngestionEventHandler(
            ingestion_service=ingestion_service,
            outbox=failing_outbox,
        )

        with pytest.raises(RuntimeError, match="outbox write failed"):
            await handler.handle("SyncStarted", _sync_started_payload())

        # Ingestion ran successfully
        assert len(ingestion_service.calls) == 1
        # No IngestionFailed event was appended
        assert len(failing_outbox.appended) == 0

    async def test_cancelled_error_propagates(
        self,
        ingestion_service: _FakeIngestionService,
        outbox: _FakeOutboxRepository,
    ):
        """asyncio.CancelledError must be re-raised, not swallowed as IngestionFailed."""

        class _CancellingService(_FakeIngestionService):
            async def run(  # type: ignore[override]
                self,
                sync_run_id: str,
                data_source_id: str,
                knowledge_graph_id: str,
                adapter_type: str,
                connection_config: dict[str, str],
                credentials_path: str | None,
                tenant_id: str | None = None,
                credentials: dict[str, str] | None = None,
                baseline_commit: str | None = None,
            ) -> JobPackageId:
                raise asyncio.CancelledError()

        handler = IngestionEventHandler(
            ingestion_service=_CancellingService(),
            outbox=outbox,
        )

        with pytest.raises(asyncio.CancelledError):
            await handler.handle("SyncStarted", _sync_started_payload())

        # No IngestionFailed event emitted — cancellation is not a service failure
        assert len(outbox.appended) == 0
