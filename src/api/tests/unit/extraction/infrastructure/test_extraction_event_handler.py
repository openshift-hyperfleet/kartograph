"""Unit tests for ExtractionEventHandler.

Tests that JobPackageProduced events trigger the extraction pipeline
and result in MutationLogProduced or ExtractionFailed being written
to the outbox.

Spec coverage:
- Requirement: Event-Driven Side Effects
- Scenario: Extraction trigger
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from extraction.infrastructure.event_handler import ExtractionEventHandler


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


class _FakeExtractionService:
    """Fake extraction service that returns a fixed log ID or raises."""

    def __init__(self, fail: bool = False, error: str = "extraction failed") -> None:
        self._fail = fail
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def run(
        self,
        sync_run_id: str,
        data_source_id: str,
        knowledge_graph_id: str,
        job_package_id: str,
    ) -> str:
        self.calls.append(
            {
                "sync_run_id": sync_run_id,
                "data_source_id": data_source_id,
                "knowledge_graph_id": knowledge_graph_id,
                "job_package_id": job_package_id,
            }
        )
        if self._fail:
            raise RuntimeError(self._error)
        return "mutation-log-001"


@pytest.fixture
def outbox() -> _FakeOutboxRepository:
    return _FakeOutboxRepository()


@pytest.fixture
def extraction_service() -> _FakeExtractionService:
    return _FakeExtractionService()


@pytest.fixture
def failing_service() -> _FakeExtractionService:
    return _FakeExtractionService(fail=True, error="AI model timeout")


@pytest.fixture
def handler(
    extraction_service: _FakeExtractionService,
    outbox: _FakeOutboxRepository,
) -> ExtractionEventHandler:
    return ExtractionEventHandler(
        extraction_service=extraction_service,
        outbox=outbox,
    )


def _job_package_produced_payload(
    sync_run_id: str = "run-001",
    job_package_id: str = "pkg-001",
) -> dict[str, Any]:
    return {
        "sync_run_id": sync_run_id,
        "data_source_id": "ds-001",
        "knowledge_graph_id": "kg-001",
        "job_package_id": job_package_id,
        "occurred_at": datetime.now(UTC).isoformat(),
    }


class TestExtractionEventHandlerSupportedEvents:
    """Tests for supported_event_types()."""

    def test_handles_job_package_produced(self, handler: ExtractionEventHandler):
        """Handler should declare support for JobPackageProduced."""
        assert "JobPackageProduced" in handler.supported_event_types()

    def test_does_not_handle_other_events(self, handler: ExtractionEventHandler):
        """Handler should only support JobPackageProduced."""
        assert handler.supported_event_types() == frozenset({"JobPackageProduced"})


@pytest.mark.asyncio
class TestExtractionEventHandlerSuccess:
    """Tests for successful extraction via JobPackageProduced event."""

    async def test_runs_extraction_on_job_package_produced(
        self,
        handler: ExtractionEventHandler,
        extraction_service: _FakeExtractionService,
    ):
        """handle('JobPackageProduced', ...) should invoke the extraction service."""
        payload = _job_package_produced_payload(
            sync_run_id="run-001", job_package_id="pkg-001"
        )
        await handler.handle("JobPackageProduced", payload)

        assert len(extraction_service.calls) == 1
        call = extraction_service.calls[0]
        assert call["sync_run_id"] == "run-001"
        assert call["job_package_id"] == "pkg-001"
        assert call["data_source_id"] == "ds-001"
        assert call["knowledge_graph_id"] == "kg-001"

    async def test_emits_mutation_log_produced_on_success(
        self,
        handler: ExtractionEventHandler,
        outbox: _FakeOutboxRepository,
    ):
        """Successful extraction should append MutationLogProduced to outbox."""
        payload = _job_package_produced_payload(sync_run_id="run-001")
        await handler.handle("JobPackageProduced", payload)

        assert len(outbox.appended) == 1
        event = outbox.appended[0]
        assert event["event_type"] == "MutationLogProduced"
        assert event["payload"]["sync_run_id"] == "run-001"
        assert event["payload"]["data_source_id"] == "ds-001"
        assert event["payload"]["knowledge_graph_id"] == "kg-001"
        assert "mutation_log_id" in event["payload"]
        assert event["payload"]["mutation_log_id"] == "mutation-log-001"

    async def test_mutation_log_produced_aggregate_type(
        self,
        handler: ExtractionEventHandler,
        outbox: _FakeOutboxRepository,
    ):
        """MutationLogProduced should have aggregate_type='sync_run'."""
        await handler.handle("JobPackageProduced", _job_package_produced_payload())

        event = outbox.appended[0]
        assert event["aggregate_type"] == "sync_run"
        assert event["aggregate_id"] == "run-001"

    async def test_ignores_unknown_event_types(
        self,
        handler: ExtractionEventHandler,
        extraction_service: _FakeExtractionService,
        outbox: _FakeOutboxRepository,
    ):
        """Handler should silently ignore unknown event types."""
        await handler.handle("SomethingElse", {"sync_run_id": "run-001"})

        assert len(extraction_service.calls) == 0
        assert len(outbox.appended) == 0


@pytest.mark.asyncio
class TestExtractionEventHandlerFailure:
    """Tests for failed extraction via JobPackageProduced event."""

    async def test_emits_extraction_failed_on_service_error(
        self,
        failing_service: _FakeExtractionService,
        outbox: _FakeOutboxRepository,
    ):
        """Service failure should append ExtractionFailed to outbox."""
        handler = ExtractionEventHandler(
            extraction_service=failing_service,
            outbox=outbox,
        )
        payload = _job_package_produced_payload(sync_run_id="run-002")
        await handler.handle("JobPackageProduced", payload)

        assert len(outbox.appended) == 1
        event = outbox.appended[0]
        assert event["event_type"] == "ExtractionFailed"
        assert event["payload"]["sync_run_id"] == "run-002"
        assert event["payload"]["data_source_id"] == "ds-001"
        assert "AI model timeout" in event["payload"]["error"]

    async def test_extraction_failed_aggregate_type(
        self,
        failing_service: _FakeExtractionService,
        outbox: _FakeOutboxRepository,
    ):
        """ExtractionFailed should have aggregate_type='sync_run'."""
        handler = ExtractionEventHandler(
            extraction_service=failing_service,
            outbox=outbox,
        )
        await handler.handle(
            "JobPackageProduced",
            _job_package_produced_payload(sync_run_id="run-003"),
        )

        event = outbox.appended[0]
        assert event["aggregate_type"] == "sync_run"
        assert event["aggregate_id"] == "run-003"
