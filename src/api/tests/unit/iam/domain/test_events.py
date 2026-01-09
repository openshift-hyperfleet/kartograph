"""Unit tests for IAM domain events (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the domain events to make these tests pass.

Domain events capture facts about things that have happened in the domain.
They are immutable and carry all the information needed to describe
the occurrence of the event.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from iam.domain.events import (
    GroupCreated,
    GroupDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
    MemberSnapshot,
)
from iam.domain.value_objects import Role


class TestGroupCreated:
    """Tests for GroupCreated domain event."""

    def test_creates_with_required_fields(self):
        """Test that GroupCreated can be created with required fields."""
        occurred_at = datetime.now(UTC)

        event = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=occurred_at,
        )

        assert event.group_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.tenant_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert event.occurred_at == occurred_at

    def test_is_immutable(self):
        """Test that GroupCreated is immutable (frozen dataclass)."""
        event = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            event.group_id = "different"  # type: ignore[misc]

    def test_equality_based_on_values(self):
        """Test that two events with same values are equal."""
        occurred_at = datetime.now(UTC)

        event1 = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=occurred_at,
        )
        event2 = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=occurred_at,
        )

        assert event1 == event2

    def test_hashable(self):
        """Test that GroupCreated is hashable (can be used in sets/dicts)."""
        event = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=datetime.now(UTC),
        )

        # Should be able to add to a set
        event_set = {event}
        assert len(event_set) == 1


class TestGroupDeleted:
    """Tests for GroupDeleted domain event."""

    def test_creates_with_required_fields(self):
        """Test that GroupDeleted can be created with required fields."""
        occurred_at = datetime.now(UTC)
        members = (
            MemberSnapshot(user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW", role=Role.ADMIN),
            MemberSnapshot(user_id="01ARZCX0P0HZGQP3MZXQQ0NNXX", role=Role.MEMBER),
        )

        event = GroupDeleted(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            members=members,
            occurred_at=occurred_at,
        )

        assert event.group_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.tenant_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert event.members == members
        assert event.occurred_at == occurred_at

    def test_is_immutable(self):
        """Test that GroupDeleted is immutable (frozen dataclass)."""
        event = GroupDeleted(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            members=(),
            occurred_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            event.group_id = "different"  # type: ignore[misc]

    def test_members_snapshot_captures_all_members(self):
        """Test that members snapshot captures all members with their roles."""
        members = (
            MemberSnapshot(user_id="admin1", role=Role.ADMIN),
            MemberSnapshot(user_id="member1", role=Role.MEMBER),
            MemberSnapshot(user_id="member2", role=Role.MEMBER),
        )

        event = GroupDeleted(
            group_id="group1",
            tenant_id="tenant1",
            members=members,
            occurred_at=datetime.now(UTC),
        )

        assert len(event.members) == 3
        # Verify member snapshot structure
        admin_snapshot = next(m for m in event.members if m.user_id == "admin1")
        assert admin_snapshot.role == Role.ADMIN


class TestMemberAdded:
    """Tests for MemberAdded domain event."""

    def test_creates_with_required_fields(self):
        """Test that MemberAdded can be created with required fields."""
        occurred_at = datetime.now(UTC)

        event = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.MEMBER,
            occurred_at=occurred_at,
        )

        assert event.group_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.user_id == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert event.role == Role.MEMBER
        assert event.occurred_at == occurred_at

    def test_role_is_role_enum(self):
        """Test that role uses the Role enum, not a string."""
        event = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.ADMIN,
            occurred_at=datetime.now(UTC),
        )

        assert isinstance(event.role, Role)
        assert event.role == Role.ADMIN

    def test_is_immutable(self):
        """Test that MemberAdded is immutable (frozen dataclass)."""
        event = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.MEMBER,
            occurred_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            event.role = Role.ADMIN  # type: ignore[misc]


class TestMemberRemoved:
    """Tests for MemberRemoved domain event."""

    def test_creates_with_required_fields(self):
        """Test that MemberRemoved can be created with required fields."""
        occurred_at = datetime.now(UTC)

        event = MemberRemoved(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.MEMBER,
            occurred_at=occurred_at,
        )

        assert event.group_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.user_id == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert event.role == Role.MEMBER
        assert event.occurred_at == occurred_at

    def test_is_immutable(self):
        """Test that MemberRemoved is immutable (frozen dataclass)."""
        event = MemberRemoved(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.MEMBER,
            occurred_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            event.user_id = "different"  # type: ignore[misc]


class TestMemberRoleChanged:
    """Tests for MemberRoleChanged domain event."""

    def test_creates_with_required_fields(self):
        """Test that MemberRoleChanged can be created with required fields."""
        occurred_at = datetime.now(UTC)

        event = MemberRoleChanged(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            old_role=Role.MEMBER,
            new_role=Role.ADMIN,
            occurred_at=occurred_at,
        )

        assert event.group_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.user_id == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert event.old_role == Role.MEMBER
        assert event.new_role == Role.ADMIN
        assert event.occurred_at == occurred_at

    def test_roles_are_role_enum(self):
        """Test that both roles use the Role enum."""
        event = MemberRoleChanged(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            old_role=Role.MEMBER,
            new_role=Role.ADMIN,
            occurred_at=datetime.now(UTC),
        )

        assert isinstance(event.old_role, Role)
        assert isinstance(event.new_role, Role)

    def test_is_immutable(self):
        """Test that MemberRoleChanged is immutable (frozen dataclass)."""
        event = MemberRoleChanged(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            old_role=Role.MEMBER,
            new_role=Role.ADMIN,
            occurred_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            event.new_role = Role.MEMBER  # type: ignore[misc]

    def test_equality_based_on_all_values(self):
        """Test that two events with same values are equal."""
        occurred_at = datetime.now(UTC)

        event1 = MemberRoleChanged(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            old_role=Role.MEMBER,
            new_role=Role.ADMIN,
            occurred_at=occurred_at,
        )
        event2 = MemberRoleChanged(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            old_role=Role.MEMBER,
            new_role=Role.ADMIN,
            occurred_at=occurred_at,
        )

        assert event1 == event2


class TestEventTypeUnion:
    """Tests for DomainEvent type alias."""

    def test_all_events_can_be_typed_as_domain_event(self):
        """Test that all event types can be used as DomainEvent."""
        from iam.domain.events import DomainEvent

        occurred_at = datetime.now(UTC)

        events: list[DomainEvent] = [
            GroupCreated(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
                occurred_at=occurred_at,
            ),
            GroupDeleted(
                group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
                tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
                members=(
                    MemberSnapshot(
                        user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW", role=Role.ADMIN
                    ),
                ),
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

        assert len(events) == 5
