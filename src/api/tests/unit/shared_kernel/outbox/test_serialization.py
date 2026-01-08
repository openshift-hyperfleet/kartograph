"""Unit tests for event serialization (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the serialization functions to make these tests pass.
"""

from datetime import UTC, datetime

import pytest

from iam.domain.events import (
    DomainEvent,
    GroupCreated,
    GroupDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
)
from iam.domain.value_objects import Role
from shared_kernel.outbox.serialization import deserialize_event, serialize_event


class TestSerializeEvent:
    """Tests for serialize_event function."""

    def test_serializes_group_created(self):
        """Test that GroupCreated is serialized correctly."""
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=occurred_at,
        )

        payload = serialize_event(event)

        assert payload["__type__"] == "GroupCreated"
        assert payload["group_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["tenant_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert payload["occurred_at"] == "2026-01-08T12:00:00+00:00"

    def test_serializes_group_deleted(self):
        """Test that GroupDeleted is serialized correctly."""
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = GroupDeleted(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=occurred_at,
        )

        payload = serialize_event(event)

        assert payload["__type__"] == "GroupDeleted"
        assert payload["group_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["tenant_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_serializes_member_added(self):
        """Test that MemberAdded is serialized correctly."""
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.MEMBER,
            occurred_at=occurred_at,
        )

        payload = serialize_event(event)

        assert payload["__type__"] == "MemberAdded"
        assert payload["group_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["user_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert payload["role"] == "member"  # Role enum serialized to string

    def test_serializes_member_removed(self):
        """Test that MemberRemoved is serialized correctly."""
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = MemberRemoved(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.ADMIN,
            occurred_at=occurred_at,
        )

        payload = serialize_event(event)

        assert payload["__type__"] == "MemberRemoved"
        assert payload["role"] == "admin"

    def test_serializes_member_role_changed(self):
        """Test that MemberRoleChanged is serialized correctly."""
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = MemberRoleChanged(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            old_role=Role.MEMBER,
            new_role=Role.ADMIN,
            occurred_at=occurred_at,
        )

        payload = serialize_event(event)

        assert payload["__type__"] == "MemberRoleChanged"
        assert payload["old_role"] == "member"
        assert payload["new_role"] == "admin"

    def test_payload_is_json_serializable(self):
        """Test that the payload can be serialized to JSON."""
        import json

        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=occurred_at,
        )

        payload = serialize_event(event)
        json_str = json.dumps(payload)

        assert isinstance(json_str, str)


class TestDeserializeEvent:
    """Tests for deserialize_event function."""

    def test_deserializes_group_created(self):
        """Test that GroupCreated is deserialized correctly."""
        payload = {
            "__type__": "GroupCreated",
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = deserialize_event(payload)

        assert isinstance(event, GroupCreated)
        assert event.group_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.tenant_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert event.occurred_at == datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)

    def test_deserializes_group_deleted(self):
        """Test that GroupDeleted is deserialized correctly."""
        payload = {
            "__type__": "GroupDeleted",
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = deserialize_event(payload)

        assert isinstance(event, GroupDeleted)

    def test_deserializes_member_added(self):
        """Test that MemberAdded is deserialized correctly."""
        payload = {
            "__type__": "MemberAdded",
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "role": "member",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = deserialize_event(payload)

        assert isinstance(event, MemberAdded)
        assert event.role == Role.MEMBER

    def test_deserializes_member_removed(self):
        """Test that MemberRemoved is deserialized correctly."""
        payload = {
            "__type__": "MemberRemoved",
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = deserialize_event(payload)

        assert isinstance(event, MemberRemoved)
        assert event.role == Role.ADMIN

    def test_deserializes_member_role_changed(self):
        """Test that MemberRoleChanged is deserialized correctly."""
        payload = {
            "__type__": "MemberRoleChanged",
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "old_role": "member",
            "new_role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = deserialize_event(payload)

        assert isinstance(event, MemberRoleChanged)
        assert event.old_role == Role.MEMBER
        assert event.new_role == Role.ADMIN

    def test_raises_for_unknown_event_type(self):
        """Test that unknown event types raise an error."""
        payload = {
            "__type__": "UnknownEvent",
            "some_field": "value",
        }

        with pytest.raises(ValueError, match="Unknown event type"):
            deserialize_event(payload)

    def test_raises_for_missing_type(self):
        """Test that missing __type__ raises an error."""
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
        }

        with pytest.raises(KeyError):
            deserialize_event(payload)


class TestRoundTrip:
    """Test serialize -> deserialize round trip."""

    def test_round_trip_group_created(self):
        """Test round trip for GroupCreated."""
        original = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        payload = serialize_event(original)
        restored = deserialize_event(payload)

        assert restored == original

    def test_round_trip_member_added(self):
        """Test round trip for MemberAdded."""
        original = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.ADMIN,
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        payload = serialize_event(original)
        restored = deserialize_event(payload)

        assert restored == original

    def test_round_trip_all_events(self):
        """Test round trip for all event types."""
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        events: list[DomainEvent] = [
            GroupCreated(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
                occurred_at=occurred_at,
            ),
            GroupDeleted(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
                occurred_at=occurred_at,
            ),
            MemberAdded(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
                role=Role.MEMBER,
                occurred_at=occurred_at,
            ),
            MemberRemoved(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
                role=Role.MEMBER,
                occurred_at=occurred_at,
            ),
            MemberRoleChanged(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
                old_role=Role.MEMBER,
                new_role=Role.ADMIN,
                occurred_at=occurred_at,
            ),
        ]

        for original in events:
            payload = serialize_event(original)
            restored = deserialize_event(payload)
            assert restored == original, f"Round trip failed for {type(original)}"
