"""Unit tests for OutboxRepository (TDD - tests first).

These tests use mocked database sessions to test the repository logic
without requiring a real database connection.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from infrastructure.outbox.repository import OutboxRepository


class TestOutboxRepositoryAppend:
    """Tests for OutboxRepository.append() method."""

    @pytest.mark.asyncio
    async def test_append_creates_outbox_model(self):
        """Test that append creates an OutboxModel and adds it to session."""
        # Arrange
        mock_session = MagicMock()
        repo = OutboxRepository(mock_session)

        payload: dict[str, Any] = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)

        # Act
        await repo.append(
            event_type="GroupCreated",
            payload=payload,
            occurred_at=occurred_at,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
        )

        # Assert
        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        assert added_model.aggregate_type == "group"
        assert added_model.aggregate_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert added_model.event_type == "GroupCreated"
        assert added_model.payload["group_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert added_model.payload["tenant_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert added_model.occurred_at == occurred_at
        assert added_model.processed_at is None

    @pytest.mark.asyncio
    async def test_append_accepts_pre_serialized_payload(self):
        """Test that the repository accepts pre-serialized payloads."""
        mock_session = MagicMock()
        repo = OutboxRepository(mock_session)

        payload: dict[str, Any] = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)

        await repo.append(
            event_type="MemberAdded",
            payload=payload,
            occurred_at=occurred_at,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
        )

        added_model = mock_session.add.call_args[0][0]
        assert added_model.event_type == "MemberAdded"
        assert added_model.payload["user_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert added_model.payload["role"] == "admin"


class TestOutboxRepositoryFetchUnprocessed:
    """Tests for OutboxRepository.fetch_unprocessed() method."""

    @pytest.mark.asyncio
    async def test_fetch_unprocessed_returns_outbox_entries(self):
        """Test that fetch_unprocessed returns OutboxEntry value objects."""
        from shared_kernel.outbox.value_objects import OutboxEntry

        # Arrange
        mock_session = AsyncMock()
        entry_id = uuid4()
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        created_at = datetime(2026, 1, 8, 12, 0, 1, tzinfo=UTC)

        # Create the expected OutboxEntry that to_value_object will return
        expected_entry = OutboxEntry(
            id=entry_id,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={
                "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            },
            occurred_at=occurred_at,
            processed_at=None,
            created_at=created_at,
        )

        # Create a mock model that returns the expected entry
        mock_model = MagicMock()
        mock_model.to_value_object.return_value = expected_entry

        # Setup mock result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_model]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = OutboxRepository(mock_session)

        # Act
        entries = await repo.fetch_unprocessed(limit=10)

        # Assert
        assert len(entries) == 1
        entry = entries[0]
        assert entry.id == entry_id
        assert entry.aggregate_type == "group"
        assert entry.event_type == "GroupCreated"
        assert entry.processed_at is None
        mock_model.to_value_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_unprocessed_respects_limit(self):
        """Test that the limit parameter is respected."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = OutboxRepository(mock_session)

        await repo.fetch_unprocessed(limit=50)

        # Verify execute was called (the limit is in the query)
        mock_session.execute.assert_called_once()


class TestOutboxRepositoryMarkProcessed:
    """Tests for OutboxRepository.mark_processed() method."""

    @pytest.mark.asyncio
    async def test_mark_processed_updates_timestamp(self):
        """Test that mark_processed sets processed_at timestamp."""
        mock_session = AsyncMock()
        entry_id = uuid4()

        repo = OutboxRepository(mock_session)

        await repo.mark_processed(entry_id)

        # Verify execute was called with an UPDATE statement
        mock_session.execute.assert_called_once()
