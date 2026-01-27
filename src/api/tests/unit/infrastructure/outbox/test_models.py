"""Unit tests for OutboxModel.

These tests verify the ORM model behavior and conversion methods.
"""

from datetime import UTC, datetime
from uuid import uuid4

from infrastructure.outbox.models import OutboxModel
from shared_kernel.outbox.value_objects import OutboxEntry


class TestOutboxModelToValueObject:
    """Tests for OutboxModel.to_value_object() method."""

    def test_converts_model_to_outbox_entry(self):
        """Should convert all fields from model to OutboxEntry."""
        entry_id = uuid4()
        occurred_at = datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC)
        created_at = datetime(2026, 1, 9, 12, 0, 1, tzinfo=UTC)

        model = OutboxModel(
            id=entry_id,
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={"group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ"},
            occurred_at=occurred_at,
            processed_at=None,
            created_at=created_at,
            retry_count=0,
            last_error=None,
            failed_at=None,
        )

        entry = model.to_value_object()

        assert isinstance(entry, OutboxEntry)
        assert entry.id == entry_id
        assert entry.aggregate_type == "group"
        assert entry.aggregate_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert entry.event_type == "GroupCreated"
        assert entry.payload == {"group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ"}
        assert entry.occurred_at == occurred_at
        assert entry.processed_at is None
        assert entry.created_at == created_at
        assert entry.retry_count == 0
        assert entry.last_error is None
        assert entry.failed_at is None

    def test_converts_processed_entry(self):
        """Should preserve processed_at when set."""
        processed_at = datetime(2026, 1, 9, 12, 5, 0, tzinfo=UTC)

        model = OutboxModel(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={},
            occurred_at=datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC),
            processed_at=processed_at,
            created_at=datetime(2026, 1, 9, 12, 0, 1, tzinfo=UTC),
            retry_count=0,
            last_error=None,
            failed_at=None,
        )

        entry = model.to_value_object()

        assert entry.processed_at == processed_at

    def test_converts_failed_entry_with_retry_info(self):
        """Should preserve retry count and error info for failed entries."""
        failed_at = datetime(2026, 1, 9, 12, 10, 0, tzinfo=UTC)

        model = OutboxModel(
            id=uuid4(),
            aggregate_type="group",
            aggregate_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            event_type="GroupCreated",
            payload={},
            occurred_at=datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC),
            processed_at=None,
            created_at=datetime(2026, 1, 9, 12, 0, 1, tzinfo=UTC),
            retry_count=5,
            last_error="SpiceDB connection failed",
            failed_at=failed_at,
        )

        entry = model.to_value_object()

        assert entry.retry_count == 5
        assert entry.last_error == "SpiceDB connection failed"
        assert entry.failed_at == failed_at
        assert entry.failed_at is not None  # Entry is in failed state
