"""Unit tests for IAMEventSerializer (TDD - tests first).

These tests verify that IAM domain events are correctly serialized
and deserialized for outbox storage.
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
    MemberSnapshot,
)
from iam.domain.value_objects import GroupRole
from iam.infrastructure.outbox import IAMEventSerializer


class TestIAMEventSerializerSupportedEvents:
    """Tests for supported event types."""

    def test_supports_all_iam_domain_events(self):
        """Serializer should support all IAM domain event types."""
        serializer = IAMEventSerializer()
        supported = serializer.supported_event_types()

        assert "GroupCreated" in supported
        assert "GroupDeleted" in supported
        assert "MemberAdded" in supported
        assert "MemberRemoved" in supported
        assert "MemberRoleChanged" in supported


class TestIAMEventSerializerSerialize:
    """Tests for serialize method."""

    def test_serializes_group_created(self):
        """GroupCreated should be serialized correctly."""
        serializer = IAMEventSerializer()
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=occurred_at,
        )

        payload = serializer.serialize(event)

        assert payload["group_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["tenant_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert payload["occurred_at"] == "2026-01-08T12:00:00+00:00"

    def test_serializes_group_deleted_with_members(self):
        """GroupDeleted should include member snapshots."""
        serializer = IAMEventSerializer()
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        members = (
            MemberSnapshot(user_id="user1", role=GroupRole.ADMIN),
            MemberSnapshot(user_id="user2", role=GroupRole.MEMBER),
        )
        event = GroupDeleted(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            members=members,
            occurred_at=occurred_at,
        )

        payload = serializer.serialize(event)

        assert payload["group_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert len(payload["members"]) == 2
        assert payload["members"][0]["user_id"] == "user1"
        assert payload["members"][0]["role"] == "admin"
        assert payload["members"][1]["role"] == "member"

    def test_serializes_member_added(self):
        """MemberAdded should serialize role enum to string."""
        serializer = IAMEventSerializer()
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=GroupRole.MEMBER,
            occurred_at=occurred_at,
        )

        payload = serializer.serialize(event)

        assert payload["group_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert payload["user_id"] == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert payload["role"] == "member"

    def test_serializes_member_role_changed(self):
        """MemberRoleChanged should serialize both roles."""
        serializer = IAMEventSerializer()
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = MemberRoleChanged(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            old_role=GroupRole.MEMBER,
            new_role=GroupRole.ADMIN,
            occurred_at=occurred_at,
        )

        payload = serializer.serialize(event)

        assert payload["old_role"] == "member"
        assert payload["new_role"] == "admin"

    def test_payload_is_json_serializable(self):
        """Serialized payload should be JSON-compatible."""
        import json

        serializer = IAMEventSerializer()
        occurred_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
        event = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=occurred_at,
        )

        payload = serializer.serialize(event)
        json_str = json.dumps(payload)

        assert isinstance(json_str, str)

    def test_raises_for_unsupported_event(self):
        """Serializer should raise for unsupported event types."""
        from dataclasses import dataclass

        serializer = IAMEventSerializer()

        @dataclass(frozen=True)
        class UnknownEvent:
            data: str

        with pytest.raises(ValueError) as exc_info:
            serializer.serialize(UnknownEvent(data="test"))

        assert "Unsupported event type" in str(exc_info.value)


class TestIAMEventSerializerDeserialize:
    """Tests for deserialize method."""

    def test_deserializes_group_created(self):
        """GroupCreated should be deserialized correctly."""
        serializer = IAMEventSerializer()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = serializer.deserialize("GroupCreated", payload)

        assert isinstance(event, GroupCreated)
        assert event.group_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.tenant_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert event.occurred_at == datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)

    def test_deserializes_group_deleted_with_members(self):
        """GroupDeleted should reconstruct member snapshots."""
        serializer = IAMEventSerializer()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "members": [
                {"user_id": "user1", "role": "admin"},
                {"user_id": "user2", "role": "member"},
            ],
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = serializer.deserialize("GroupDeleted", payload)

        assert isinstance(event, GroupDeleted)
        assert len(event.members) == 2
        assert isinstance(event.members, tuple)
        assert isinstance(event.members[0], MemberSnapshot)
        assert event.members[0].role == GroupRole.ADMIN
        assert event.members[1].role == GroupRole.MEMBER

    def test_deserializes_member_added(self):
        """MemberAdded should reconstruct Role enum."""
        serializer = IAMEventSerializer()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "role": "member",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = serializer.deserialize("MemberAdded", payload)

        assert isinstance(event, MemberAdded)
        assert event.role == GroupRole.MEMBER

    def test_deserializes_member_role_changed(self):
        """MemberRoleChanged should reconstruct both roles."""
        serializer = IAMEventSerializer()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "old_role": "member",
            "new_role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        event = serializer.deserialize("MemberRoleChanged", payload)

        assert isinstance(event, MemberRoleChanged)
        assert event.old_role == GroupRole.MEMBER
        assert event.new_role == GroupRole.ADMIN

    def test_raises_for_unknown_event_type(self):
        """Deserializer should raise for unknown event types."""
        serializer = IAMEventSerializer()

        with pytest.raises(ValueError) as exc_info:
            serializer.deserialize("UnknownEvent", {})

        assert "Unsupported event type" in str(exc_info.value)


class TestIAMEventSerializerRoundTrip:
    """Test serialize -> deserialize round trip."""

    def test_round_trip_group_created(self):
        """GroupCreated should round trip correctly."""
        serializer = IAMEventSerializer()
        original = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("GroupCreated", payload)

        assert restored == original

    def test_round_trip_group_deleted(self):
        """GroupDeleted should round trip with members."""
        serializer = IAMEventSerializer()
        members = (
            MemberSnapshot(user_id="user1", role=GroupRole.ADMIN),
            MemberSnapshot(user_id="user2", role=GroupRole.MEMBER),
        )
        original = GroupDeleted(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            members=members,
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("GroupDeleted", payload)

        assert restored == original

    def test_round_trip_all_events(self):
        """All event types should round trip correctly."""
        serializer = IAMEventSerializer()
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
                members=(),
                occurred_at=occurred_at,
            ),
            MemberAdded(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
                role=GroupRole.MEMBER,
                occurred_at=occurred_at,
            ),
            MemberRemoved(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
                role=GroupRole.MEMBER,
                occurred_at=occurred_at,
            ),
            MemberRoleChanged(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
                old_role=GroupRole.MEMBER,
                new_role=GroupRole.ADMIN,
                occurred_at=occurred_at,
            ),
        ]

        for original in events:
            event_type = type(original).__name__
            payload = serializer.serialize(original)
            restored = serializer.deserialize(event_type, payload)
            assert restored == original, f"Round trip failed for {event_type}"
