"""Unit tests for Outbox value objects (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the value objects to make these tests pass.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from shared_kernel.outbox.value_objects import OutboxEntry


class TestOutboxEntry:
    """Tests for OutboxEntry value object."""

    def test_creates_with_required_fields(self):
        """Test that OutboxEntry can be created with required fields."""
        entry_id = uuid4()
        occurred_at = datetime.now(UTC)
        created_at = datetime.now(UTC)

        entry = OutboxEntry(
            id=entry_id,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="MemberAdded",
            payload={"user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW", "role": "member"},
            occurred_at=occurred_at,
            processed_at=None,
            created_at=created_at,
        )

        assert entry.id == entry_id
        assert entry.aggregate_type == "group"
        assert entry.aggregate_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert entry.event_type == "MemberAdded"
        assert entry.payload == {
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "role": "member",
        }
        assert entry.occurred_at == occurred_at
        assert entry.processed_at is None
        assert entry.created_at == created_at

    def test_id_is_uuid(self):
        """Test that id is a UUID type."""
        entry = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={"tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY"},
            occurred_at=datetime.now(UTC),
            processed_at=None,
            created_at=datetime.now(UTC),
        )

        assert isinstance(entry.id, UUID)

    def test_is_immutable(self):
        """Test that OutboxEntry is immutable (frozen dataclass)."""
        entry = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={"tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY"},
            occurred_at=datetime.now(UTC),
            processed_at=None,
            created_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            entry.event_type = "different"  # type: ignore[misc]

    def test_processed_at_can_be_set(self):
        """Test that processed_at can hold a datetime when entry is processed."""
        processed_at = datetime.now(UTC)

        entry = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={"tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY"},
            occurred_at=datetime.now(UTC),
            processed_at=processed_at,
            created_at=datetime.now(UTC),
        )

        assert entry.processed_at == processed_at

    def test_equality_based_on_values(self):
        """Test that two entries with same values are equal."""
        entry_id = uuid4()
        occurred_at = datetime.now(UTC)
        created_at = datetime.now(UTC)
        payload = {"tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY"}

        entry1 = OutboxEntry(
            id=entry_id,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload=payload,
            occurred_at=occurred_at,
            processed_at=None,
            created_at=created_at,
        )
        entry2 = OutboxEntry(
            id=entry_id,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload=payload,
            occurred_at=occurred_at,
            processed_at=None,
            created_at=created_at,
        )

        assert entry1 == entry2

    def test_payload_is_dict(self):
        """Test that payload is a dictionary type.

        Note: OutboxEntry with dict payload is not hashable because dicts
        are mutable. This is acceptable as we don't need to use OutboxEntry
        in sets or as dict keys.
        """
        entry = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={"tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY"},
            occurred_at=datetime.now(UTC),
            processed_at=None,
            created_at=datetime.now(UTC),
        )

        assert isinstance(entry.payload, dict)
        assert entry.payload["tenant_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_is_processed_property(self):
        """Test that we can check if entry is processed."""
        unprocessed_entry = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={},
            occurred_at=datetime.now(UTC),
            processed_at=None,
            created_at=datetime.now(UTC),
        )

        processed_entry = OutboxEntry(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={},
            occurred_at=datetime.now(UTC),
            processed_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )

        assert unprocessed_entry.is_processed is False
        assert processed_entry.is_processed is True
