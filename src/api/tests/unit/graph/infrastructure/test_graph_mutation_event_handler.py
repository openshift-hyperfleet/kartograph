"""Unit tests for GraphMutationEventHandler.

Tests that MutationLogProduced events trigger mutation application
and result in MutationsApplied or MutationApplicationFailed being written
to the outbox.

Spec coverage:
- Requirement: Event-Driven Side Effects
- Scenario: Mutation trigger
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from graph.infrastructure.event_handler import GraphMutationEventHandler


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


class _FakeMutationLogApplier:
    """Fake mutation log applier that returns success or raises."""

    def __init__(self, fail: bool = False, error: str = "DB write error") -> None:
        self._fail = fail
        self._error = error
        self.calls: list[str] = []

    async def apply_mutation_log(self, mutation_log_id: str) -> bool:
        self.calls.append(mutation_log_id)
        if self._fail:
            raise RuntimeError(self._error)
        return True


@pytest.fixture
def outbox() -> _FakeOutboxRepository:
    return _FakeOutboxRepository()


@pytest.fixture
def applier() -> _FakeMutationLogApplier:
    return _FakeMutationLogApplier()


@pytest.fixture
def failing_applier() -> _FakeMutationLogApplier:
    return _FakeMutationLogApplier(fail=True, error="DB write error")


@pytest.fixture
def handler(
    applier: _FakeMutationLogApplier,
    outbox: _FakeOutboxRepository,
) -> GraphMutationEventHandler:
    return GraphMutationEventHandler(
        mutation_log_applier=applier,
        outbox=outbox,
    )


def _mutation_log_produced_payload(
    sync_run_id: str = "run-001",
    mutation_log_id: str = "log-001",
) -> dict[str, Any]:
    return {
        "sync_run_id": sync_run_id,
        "data_source_id": "ds-001",
        "knowledge_graph_id": "kg-001",
        "mutation_log_id": mutation_log_id,
        "occurred_at": datetime.now(UTC).isoformat(),
    }


class TestGraphMutationEventHandlerSupportedEvents:
    """Tests for supported_event_types()."""

    def test_handles_mutation_log_produced(self, handler: GraphMutationEventHandler):
        """Handler should declare support for MutationLogProduced."""
        assert "MutationLogProduced" in handler.supported_event_types()

    def test_does_not_handle_other_events(self, handler: GraphMutationEventHandler):
        """Handler should only support MutationLogProduced."""
        assert handler.supported_event_types() == frozenset({"MutationLogProduced"})


@pytest.mark.asyncio
class TestGraphMutationEventHandlerSuccess:
    """Tests for successful mutation application."""

    async def test_applies_mutation_log_on_event(
        self,
        handler: GraphMutationEventHandler,
        applier: _FakeMutationLogApplier,
    ):
        """handle('MutationLogProduced', ...) should invoke the mutation applier."""
        payload = _mutation_log_produced_payload(
            sync_run_id="run-001", mutation_log_id="log-001"
        )
        await handler.handle("MutationLogProduced", payload)

        assert len(applier.calls) == 1
        assert applier.calls[0] == "log-001"

    async def test_emits_mutations_applied_on_success(
        self,
        handler: GraphMutationEventHandler,
        outbox: _FakeOutboxRepository,
    ):
        """Successful application should append MutationsApplied to outbox."""
        payload = _mutation_log_produced_payload(sync_run_id="run-001")
        await handler.handle("MutationLogProduced", payload)

        assert len(outbox.appended) == 1
        event = outbox.appended[0]
        assert event["event_type"] == "MutationsApplied"
        assert event["payload"]["sync_run_id"] == "run-001"
        assert event["payload"]["data_source_id"] == "ds-001"
        assert event["payload"]["knowledge_graph_id"] == "kg-001"

    async def test_mutations_applied_aggregate_type(
        self,
        handler: GraphMutationEventHandler,
        outbox: _FakeOutboxRepository,
    ):
        """MutationsApplied should have aggregate_type='sync_run'."""
        await handler.handle("MutationLogProduced", _mutation_log_produced_payload())

        event = outbox.appended[0]
        assert event["aggregate_type"] == "sync_run"
        assert event["aggregate_id"] == "run-001"

    async def test_ignores_unknown_event_types(
        self,
        handler: GraphMutationEventHandler,
        applier: _FakeMutationLogApplier,
        outbox: _FakeOutboxRepository,
    ):
        """Handler should silently ignore unknown event types."""
        await handler.handle("SomethingElse", {"sync_run_id": "run-001"})

        assert len(applier.calls) == 0
        assert len(outbox.appended) == 0


@pytest.mark.asyncio
class TestGraphMutationEventHandlerFailure:
    """Tests for failed mutation application."""

    async def test_emits_mutation_application_failed_on_error(
        self,
        failing_applier: _FakeMutationLogApplier,
        outbox: _FakeOutboxRepository,
    ):
        """Applier failure should append MutationApplicationFailed to outbox."""
        handler = GraphMutationEventHandler(
            mutation_log_applier=failing_applier,
            outbox=outbox,
        )
        payload = _mutation_log_produced_payload(sync_run_id="run-002")
        await handler.handle("MutationLogProduced", payload)

        assert len(outbox.appended) == 1
        event = outbox.appended[0]
        assert event["event_type"] == "MutationApplicationFailed"
        assert event["payload"]["sync_run_id"] == "run-002"
        assert event["payload"]["data_source_id"] == "ds-001"
        assert "DB write error" in event["payload"]["error"]

    async def test_mutation_application_failed_aggregate_type(
        self,
        failing_applier: _FakeMutationLogApplier,
        outbox: _FakeOutboxRepository,
    ):
        """MutationApplicationFailed should have aggregate_type='sync_run'."""
        handler = GraphMutationEventHandler(
            mutation_log_applier=failing_applier,
            outbox=outbox,
        )
        await handler.handle(
            "MutationLogProduced",
            _mutation_log_produced_payload(sync_run_id="run-003"),
        )

        event = outbox.appended[0]
        assert event["aggregate_type"] == "sync_run"
        assert event["aggregate_id"] == "run-003"
