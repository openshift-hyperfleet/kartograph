"""Unit tests for IngestionEventHandler.

Tests that SyncStarted events trigger the ingestion pipeline
and result in JobPackageProduced or IngestionFailed being written to outbox.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from ingestion.infrastructure.event_handler import IngestionEventHandler
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
    ) -> JobPackageId:
        self.calls.append(
            {
                "sync_run_id": sync_run_id,
                "data_source_id": data_source_id,
                "knowledge_graph_id": knowledge_graph_id,
                "adapter_type": adapter_type,
            }
        )
        if self._fail:
            raise RuntimeError(self._error)
        return JobPackageId(value="01HRZZZZZZZZZZZZZZZZZZZZZ0")


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
