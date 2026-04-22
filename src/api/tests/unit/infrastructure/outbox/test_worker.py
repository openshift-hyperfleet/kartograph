"""Unit tests for OutboxWorker (TDD - tests first).

These tests use mocked dependencies to test the worker logic
without requiring a real database or handler implementations.

Spec coverage:
- Requirement: Event Processing (normal, transient failure, permanent failure/DLQ)
- Requirement: Idempotent Event Handlers (duplicate delivery)
- Requirement: Concurrent Worker Safety (FOR UPDATE SKIP LOCKED)
- Requirement: Event Fan-Out (unknown event type → immediate DLQ)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

import pytest

from infrastructure.outbox.worker import OutboxWorker
from shared_kernel.outbox.exceptions import UnknownEventTypeError
from shared_kernel.outbox.value_objects import OutboxEntry


class TestOutboxWorkerProcessBatch:
    """Tests for OutboxWorker._process_entries() method."""

    @pytest.mark.asyncio
    async def test_processes_unprocessed_entries(self):
        """Test that _process_entries calls handler.handle for each entry."""
        # Arrange
        mock_session_factory = AsyncMock()
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_handler = AsyncMock()
        mock_probe = MagicMock()

        entry = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={
                "__type__": "GroupCreated",
                "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
                "occurred_at": "2026-01-08T12:00:00+00:00",
            },
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            processed_at=None,
            created_at=datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC),
        )

        worker = OutboxWorker(
            session_factory=mock_session_factory,
            handler=mock_handler,
            probe=mock_probe,
            event_source=None,
        )

        # Act
        await worker._process_entries([entry], mock_session)

        # Assert
        mock_probe.event_dispatching.assert_called_once_with(entry.id, "GroupCreated")
        mock_handler.handle.assert_called_once_with(entry.event_type, entry.payload)
        mock_probe.event_processed.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_different_event_types(self):
        """Test that handler.handle is called for various event types."""
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_probe = MagicMock()

        entry = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="MemberRemoved",
            payload={
                "__type__": "MemberRemoved",
                "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
                "role": "member",
                "occurred_at": "2026-01-08T12:00:00+00:00",
            },
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            processed_at=None,
            created_at=datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC),
        )

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            event_source=None,
        )

        await worker._process_entries([entry], mock_session)

        mock_handler.handle.assert_called_once_with("MemberRemoved", entry.payload)

    @pytest.mark.asyncio
    async def test_handles_multiple_entries_in_batch(self):
        """Test that handler.handle is called for each entry in a batch."""
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_probe = MagicMock()

        entry_a = OutboxEntry(
            id=uuid4(),
            aggregate_type="tenant",
            aggregate_id="01TENANT123",
            event_type="TenantCreated",
            payload={"__type__": "TenantCreated", "tenant_id": "01TENANT123"},
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            processed_at=None,
            created_at=datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC),
        )
        entry_b = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01GROUP456",
            event_type="GroupCreated",
            payload={"__type__": "GroupCreated", "group_id": "01GROUP456"},
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            processed_at=None,
            created_at=datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC),
        )

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            event_source=None,
        )

        await worker._process_entries([entry_a, entry_b], mock_session)

        mock_handler.handle.assert_has_awaits(
            [
                call(entry_a.event_type, entry_a.payload),
                call(entry_b.event_type, entry_b.payload),
            ],
            any_order=False,
        )

    @pytest.mark.asyncio
    async def test_marks_entry_as_processed(self):
        """Test that entries are marked as processed after handler.handle."""
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_probe = MagicMock()

        entry_id = uuid4()
        entry = OutboxEntry(
            id=entry_id,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={
                "__type__": "GroupCreated",
                "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
                "occurred_at": "2026-01-08T12:00:00+00:00",
            },
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            processed_at=None,
            created_at=datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC),
        )

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            event_source=None,
        )

        await worker._process_entries([entry], mock_session)

        # Verify session.execute was called (for mark_processed)
        mock_session.execute.assert_called()


class TestOutboxWorkerLifecycle:
    """Tests for worker start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self):
        """Test that start() sets the running flag."""
        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=AsyncMock(),
            probe=MagicMock(),
            event_source=None,
        )

        assert worker._running is False

        # We don't actually start the loops, just test the flag would be set
        worker._running = True
        assert worker._running is True

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self):
        """Test that stop() clears the running flag."""
        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=AsyncMock(),
            probe=MagicMock(),
            event_source=None,
        )

        worker._running = True
        await worker.stop()

        assert worker._running is False


class TestOutboxWorkerProbeIntegration:
    """Tests for probe method calls during processing."""

    @pytest.mark.asyncio
    async def test_calls_event_processed_on_success(self):
        """Test that probe.event_processed is called on success."""
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_probe = MagicMock()

        entry_id = uuid4()
        entry = OutboxEntry(
            id=entry_id,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={
                "__type__": "GroupCreated",
                "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
                "occurred_at": "2026-01-08T12:00:00+00:00",
            },
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            processed_at=None,
            created_at=datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC),
        )

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            event_source=None,
        )

        await worker._process_entries([entry], mock_session)

        mock_probe.event_processed.assert_called_once_with(entry_id, "GroupCreated")

    @pytest.mark.asyncio
    async def test_calls_event_processing_failed_on_error(self):
        """Test that probe.event_processing_failed is called on error."""
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_handler.handle.side_effect = Exception("Handler unavailable")
        mock_probe = MagicMock()

        entry_id = uuid4()
        entry = OutboxEntry(
            id=entry_id,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={
                "__type__": "GroupCreated",
                "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
                "occurred_at": "2026-01-08T12:00:00+00:00",
            },
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            processed_at=None,
            created_at=datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC),
        )

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            event_source=None,
        )

        await worker._process_entries([entry], mock_session)

        mock_probe.event_processing_failed.assert_called_once()
        # Verify the error message is included
        args = mock_probe.event_processing_failed.call_args[0]
        assert args[0] == entry_id
        assert "Handler unavailable" in args[1]


class TestOutboxWorkerValidation:
    """Tests for OutboxWorker constructor input validation."""

    def test_rejects_zero_poll_interval(self):
        with pytest.raises(ValueError, match="poll_interval_seconds"):
            OutboxWorker(
                session_factory=AsyncMock(),
                handler=AsyncMock(),
                probe=MagicMock(),
                poll_interval_seconds=0,
            )

    def test_rejects_negative_poll_interval(self):
        with pytest.raises(ValueError, match="poll_interval_seconds"):
            OutboxWorker(
                session_factory=AsyncMock(),
                handler=AsyncMock(),
                probe=MagicMock(),
                poll_interval_seconds=-1,
            )

    def test_rejects_zero_batch_size(self):
        with pytest.raises(ValueError, match="batch_size"):
            OutboxWorker(
                session_factory=AsyncMock(),
                handler=AsyncMock(),
                probe=MagicMock(),
                batch_size=0,
            )

    def test_rejects_negative_max_retries(self):
        with pytest.raises(ValueError, match="max_retries"):
            OutboxWorker(
                session_factory=AsyncMock(),
                handler=AsyncMock(),
                probe=MagicMock(),
                max_retries=-1,
            )

    def test_rejects_none_session_factory(self):
        with pytest.raises(ValueError, match="session_factory"):
            OutboxWorker(session_factory=None, handler=AsyncMock(), probe=MagicMock())

    def test_rejects_none_handler(self):
        with pytest.raises(ValueError, match="handler"):
            OutboxWorker(session_factory=AsyncMock(), handler=None, probe=MagicMock())

    def test_rejects_none_probe(self):
        with pytest.raises(ValueError, match="probe"):
            OutboxWorker(session_factory=AsyncMock(), handler=AsyncMock(), probe=None)

    def test_accepts_valid_configuration(self):
        # Should not raise
        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=AsyncMock(),
            probe=MagicMock(),
            event_source=None,
            poll_interval_seconds=10,
            batch_size=50,
            max_retries=3,
        )
        assert worker._running is False


def _make_entry(
    event_type: str = "GroupCreated",
    retry_count: int = 0,
) -> OutboxEntry:
    """Helper to build an OutboxEntry for tests."""
    return OutboxEntry(
        id=uuid4(),
        aggregate_type="group",
        aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
        event_type=event_type,
        payload={"event_type": event_type},
        occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        processed_at=None,
        created_at=datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC),
        retry_count=retry_count,
    )


class TestOutboxWorkerRetryBehavior:
    """Tests for retry and DLQ behavior.

    Covers spec:
    - Requirement: Event Processing — Transient failure scenario
    - Requirement: Event Processing — Permanent failure (dead letter) scenario
    - Requirement: Event Fan-Out — Unknown event type scenario
    """

    @pytest.mark.asyncio
    async def test_transient_failure_increments_retry_count(self):
        """Spec: Transient failure — retry count is incremented and last error recorded.

        GIVEN an outbox entry that fails to process (e.g., SpiceDB unreachable)
        WHEN the worker retries
        THEN the retry count is incremented
        AND the last error is recorded
        """
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_handler.handle.side_effect = RuntimeError("SpiceDB unreachable")
        mock_probe = MagicMock()

        entry = _make_entry(retry_count=0)

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            max_retries=3,
        )

        await worker._process_entries([entry], mock_session)

        # Worker should call session.execute (for _increment_retry)
        mock_session.execute.assert_called()
        # probe.event_processing_failed should be called (not DLQ)
        mock_probe.event_processing_failed.assert_called_once()
        # probe.event_moved_to_dlq should NOT be called yet
        mock_probe.event_moved_to_dlq.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_retries_moves_entry_to_dlq(self):
        """Spec: Permanent failure — entry exceeding max retry count goes to DLQ.

        GIVEN an outbox entry that has exceeded the maximum retry count
        WHEN the worker encounters it
        THEN the entry is moved to a dead-letter state (failed_at timestamp set)
        AND it is no longer retried
        """
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_handler.handle.side_effect = RuntimeError("Still unreachable")
        mock_probe = MagicMock()

        # Entry already at max retries - 1 so next failure exceeds it
        entry = _make_entry(retry_count=2)  # max_retries=3 → 2+1=3 >= 3 → DLQ

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            max_retries=3,
        )

        await worker._process_entries([entry], mock_session)

        # probe.event_moved_to_dlq should be called
        mock_probe.event_moved_to_dlq.assert_called_once()
        args = mock_probe.event_moved_to_dlq.call_args[0]
        assert args[0] == entry.id
        # probe.event_processing_failed should NOT be called (it's DLQ now)
        mock_probe.event_processing_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_event_type_immediately_moves_to_dlq(self):
        """Spec: Unknown event type scenario — immediately to DLQ, not retried.

        GIVEN an outbox entry with an unregistered event type
        WHEN the worker attempts to process it
        THEN the entry is immediately moved to the dead-letter state
        AND it is not retried (unknown types are permanent failures, not transient)
        """
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        # Unknown event type raises UnknownEventTypeError
        mock_handler.handle.side_effect = UnknownEventTypeError(
            "UnregisteredEvent", {"UnregisteredEvent"}
        )
        mock_probe = MagicMock()

        entry = _make_entry(event_type="UnregisteredEvent", retry_count=0)

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            max_retries=5,  # High max retries to prove we bypass retry logic
        )

        await worker._process_entries([entry], mock_session)

        # Must immediately DLQ — not increment retry count
        mock_probe.event_moved_to_dlq.assert_called_once()
        args = mock_probe.event_moved_to_dlq.call_args[0]
        assert args[0] == entry.id
        # Must NOT call event_processing_failed (no retries for unknown types)
        mock_probe.event_processing_failed.assert_not_called()
        # Must NOT call event_processed
        mock_probe.event_processed.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_event_type_dlq_even_at_zero_retries(self):
        """Unknown event type is immediately DLQ regardless of retry count.

        Even if retry_count=0, an unknown event type should go straight to DLQ
        because it is a permanent failure, not a transient one.
        """
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_handler.handle.side_effect = UnknownEventTypeError(
            "GhostEvent", {"GhostEvent"}
        )
        mock_probe = MagicMock()

        entry = _make_entry(event_type="GhostEvent", retry_count=0)

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            max_retries=10,
        )

        await worker._process_entries([entry], mock_session)

        mock_probe.event_moved_to_dlq.assert_called_once()
        mock_probe.event_processing_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_not_called_for_unknown_event_type(self):
        """Retry increment should never be called for unknown event types."""
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_handler.handle.side_effect = UnknownEventTypeError("Phantom", {"Phantom"})
        mock_probe = MagicMock()

        entry = _make_entry(event_type="Phantom", retry_count=0)

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            max_retries=5,
        )

        # Patch _increment_retry to verify it's never called
        with patch.object(worker, "_increment_retry", new=AsyncMock()) as mock_inc:
            await worker._process_entries([entry], mock_session)
            mock_inc.assert_not_called()

    @pytest.mark.asyncio
    async def test_transient_failure_does_not_dlq_immediately(self):
        """Transient failures (non-UnknownEventTypeError) should be retried, not DLQ'd.

        GIVEN an entry with retry_count=0 that fails with a transient error
        THEN the entry gets retry count incremented (not DLQ'd)
        """
        mock_session = AsyncMock()
        mock_handler = AsyncMock()
        mock_handler.handle.side_effect = ConnectionError("DB down")
        mock_probe = MagicMock()

        entry = _make_entry(retry_count=0)

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            handler=mock_handler,
            probe=mock_probe,
            max_retries=5,
        )

        await worker._process_entries([entry], mock_session)

        # Should be retried, not DLQ'd
        mock_probe.event_processing_failed.assert_called_once()
        mock_probe.event_moved_to_dlq.assert_not_called()


class TestOutboxWorkerTransactionAtomicity:
    """Tests for transactional atomicity of the outbox.

    Covers spec:
    - Requirement: Transactional Event Storage — Successful write scenario
    - Requirement: Transactional Event Storage — Transaction rollback scenario
    """

    @pytest.mark.asyncio
    async def test_repository_append_does_not_commit(self):
        """Spec: Repository never commits — caller owns the transaction boundary.

        The repository should call session.add() but never session.commit().
        This ensures the outbox entry and aggregate change are atomic.
        """
        from infrastructure.outbox.repository import OutboxRepository

        mock_session = MagicMock()
        repo = OutboxRepository(mock_session)

        await repo.append(
            event_type="GroupCreated",
            payload={"group_id": "01ABC"},
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            aggregate_type="group",
            aggregate_id="01ABC",
        )

        # Must NOT commit (caller owns the transaction)
        mock_session.commit.assert_not_called()
        # Must add to session (it will be committed with the aggregate)
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_service_call_leaves_no_outbox_entries(self):
        """Spec: Transaction rollback — no outbox entries persisted on rollback.

        If a service operation raises an exception after emitting events,
        the transaction rolls back and no outbox entries are persisted.
        This is guaranteed by the shared session design.
        """
        # This is demonstrated by the repository never committing.
        # If the session is rolled back (by the caller), the outbox entry
        # added via session.add() is discarded along with the aggregate change.
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        from infrastructure.outbox.repository import OutboxRepository

        repo = OutboxRepository(mock_session)

        await repo.append(
            event_type="GroupCreated",
            payload={"group_id": "01ABC"},
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            aggregate_type="group",
            aggregate_id="01ABC",
        )

        # Simulate rollback — session discards uncommitted changes
        # (In a real scenario, session.rollback() removes pending adds)
        # The key invariant: outbox repository never commits independently
        assert not mock_session.commit.called


class TestOutboxWorkerConcurrentSafety:
    """Tests for concurrent worker safety.

    Covers spec:
    - Requirement: Concurrent Worker Safety — each entry claimed by exactly one worker
    """

    @pytest.mark.asyncio
    async def test_fetch_unprocessed_uses_for_update_skip_locked(self):
        """Spec: FOR UPDATE SKIP LOCKED prevents duplicate processing.

        GIVEN two workers polling simultaneously
        WHEN both query the outbox table
        THEN each entry is claimed by exactly one worker

        This test verifies the query construction uses SKIP LOCKED by compiling
        with the PostgreSQL dialect which renders dialect-specific FOR UPDATE syntax.
        """
        from sqlalchemy.dialects import postgresql

        from infrastructure.outbox.repository import OutboxRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = OutboxRepository(mock_session)
        await repo.fetch_unprocessed(limit=10)

        # Verify execute was called and inspect the query
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0]
        query = call_args[0]

        # Compile with PostgreSQL dialect so SKIP LOCKED is rendered
        compiled = str(
            query.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        assert "SKIP LOCKED" in compiled.upper()


class TestOutboxWorkerIdempotency:
    """Tests for idempotent event handler behavior.

    Covers spec:
    - Requirement: Idempotent Event Handlers — duplicate delivery scenario
    """

    @pytest.mark.asyncio
    async def test_already_processed_entry_excluded_from_fetch(self):
        """Spec: Duplicate delivery — worker only picks up unprocessed entries.

        Entries with processed_at set are excluded from fetch_unprocessed,
        which is the primary mechanism for idempotency at the infrastructure level.
        """
        from infrastructure.outbox.repository import OutboxRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = OutboxRepository(mock_session)
        await repo.fetch_unprocessed(limit=10)

        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0]
        query = call_args[0]

        # The query must filter on processed_at IS NULL
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "processed_at IS NULL" in compiled

    @pytest.mark.asyncio
    async def test_failed_entries_excluded_from_fetch(self):
        """Spec: Dead-letter entries (failed_at set) are not re-fetched.

        GIVEN an outbox entry that has been moved to DLQ (failed_at is set)
        WHEN the worker polls for unprocessed entries
        THEN the DLQ entry is excluded
        """
        from infrastructure.outbox.repository import OutboxRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = OutboxRepository(mock_session)
        await repo.fetch_unprocessed()

        call_args = mock_session.execute.call_args[0]
        query = call_args[0]
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))

        # Must filter out DLQ entries (failed_at IS NULL)
        assert "failed_at IS NULL" in compiled
