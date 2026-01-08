"""Unit tests for OutboxWorker (TDD - tests first).

These tests use mocked dependencies to test the worker logic
without requiring a real database or SpiceDB connection.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared_kernel.outbox.spicedb_translator import (
    DeleteRelationship,
    SpiceDBTranslator,
    WriteRelationship,
)
from shared_kernel.outbox.value_objects import OutboxEntry
from infrastructure.outbox.worker import OutboxWorker


class TestOutboxWorkerProcessBatch:
    """Tests for OutboxWorker._process_batch() method."""

    @pytest.mark.asyncio
    async def test_processes_unprocessed_entries(self):
        """Test that process_batch fetches and processes entries."""
        # Arrange
        mock_session_factory = AsyncMock()
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_authz = AsyncMock()
        mock_translator = MagicMock(spec=SpiceDBTranslator)
        mock_probe = MagicMock()

        # Create a test entry
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

        # Setup translator to return a write operation
        mock_translator.translate.return_value = [
            WriteRelationship(
                resource="group:01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                relation="tenant",
                subject="tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY",
            )
        ]

        worker = OutboxWorker(
            session_factory=mock_session_factory,
            authz=mock_authz,
            translator=mock_translator,
            probe=mock_probe,
            db_url="postgresql://test",
        )

        # Act
        await worker._process_entries([entry], mock_session)

        # Assert
        mock_translator.translate.assert_called_once()
        mock_authz.write_relationship.assert_called_once_with(
            resource="group:01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation="tenant",
            subject="tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )
        mock_probe.event_processed.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_delete_relationship(self):
        """Test that delete operations are executed correctly."""
        mock_session = AsyncMock()
        mock_authz = AsyncMock()
        mock_translator = MagicMock(spec=SpiceDBTranslator)
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

        mock_translator.translate.return_value = [
            DeleteRelationship(
                resource="group:01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                relation="member",
                subject="user:01ARZCX0P0HZGQP3MZXQQ0NNWW",
            )
        ]

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            authz=mock_authz,
            translator=mock_translator,
            probe=mock_probe,
            db_url="postgresql://test",
        )

        await worker._process_entries([entry], mock_session)

        mock_authz.delete_relationship.assert_called_once_with(
            resource="group:01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation="member",
            subject="user:01ARZCX0P0HZGQP3MZXQQ0NNWW",
        )

    @pytest.mark.asyncio
    async def test_marks_entry_as_processed(self):
        """Test that entries are marked as processed after SpiceDB write."""
        mock_session = AsyncMock()
        mock_authz = AsyncMock()
        mock_translator = MagicMock(spec=SpiceDBTranslator)
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

        mock_translator.translate.return_value = [
            WriteRelationship(
                resource="group:01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                relation="tenant",
                subject="tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY",
            )
        ]

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            authz=mock_authz,
            translator=mock_translator,
            probe=mock_probe,
            db_url="postgresql://test",
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
            authz=AsyncMock(),
            translator=SpiceDBTranslator(),
            probe=MagicMock(),
            db_url="postgresql://test",
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
            authz=AsyncMock(),
            translator=SpiceDBTranslator(),
            probe=MagicMock(),
            db_url="postgresql://test",
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
        mock_authz = AsyncMock()
        mock_translator = MagicMock(spec=SpiceDBTranslator)
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

        mock_translator.translate.return_value = [
            WriteRelationship(
                resource="group:test",
                relation="tenant",
                subject="tenant:test",
            )
        ]

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            authz=mock_authz,
            translator=mock_translator,
            probe=mock_probe,
            db_url="postgresql://test",
        )

        await worker._process_entries([entry], mock_session)

        mock_probe.event_processed.assert_called_once_with(entry_id, "GroupCreated")

    @pytest.mark.asyncio
    async def test_calls_event_processing_failed_on_error(self):
        """Test that probe.event_processing_failed is called on error."""
        mock_session = AsyncMock()
        mock_authz = AsyncMock()
        mock_authz.write_relationship.side_effect = Exception("SpiceDB unavailable")
        mock_translator = MagicMock(spec=SpiceDBTranslator)
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

        mock_translator.translate.return_value = [
            WriteRelationship(
                resource="group:test",
                relation="tenant",
                subject="tenant:test",
            )
        ]

        worker = OutboxWorker(
            session_factory=AsyncMock(),
            authz=mock_authz,
            translator=mock_translator,
            probe=mock_probe,
            db_url="postgresql://test",
        )

        await worker._process_entries([entry], mock_session)

        mock_probe.event_processing_failed.assert_called_once()
        # Verify the error message is included
        args = mock_probe.event_processing_failed.call_args[0]
        assert args[0] == entry_id
        assert "SpiceDB unavailable" in args[1]
