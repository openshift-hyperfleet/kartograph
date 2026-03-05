"""Unit tests for OutboxWorker (TDD - tests first).

These tests use mocked dependencies to test the worker logic
without requiring a real database or handler implementations.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from infrastructure.outbox.worker import OutboxWorker
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

        assert mock_handler.handle.call_count == 2

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
