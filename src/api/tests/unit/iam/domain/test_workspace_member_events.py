"""Unit tests for workspace member domain events (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the domain events to make these tests pass.

Workspace member events capture facts about membership changes
in workspaces. They support both direct user grants and group-based
grants via the member_type field.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from iam.domain.events import (
    WorkspaceMemberAdded,
    WorkspaceMemberRemoved,
    WorkspaceMemberRoleChanged,
)
from iam.domain.value_objects import MemberType, WorkspaceRole


class TestWorkspaceMemberAdded:
    """Tests for WorkspaceMemberAdded domain event."""

    def test_creates_with_required_fields(self):
        """Test that WorkspaceMemberAdded can be created with required fields."""
        occurred_at = datetime.now(UTC)

        event = WorkspaceMemberAdded(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
            occurred_at=occurred_at,
        )

        assert event.workspace_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.member_id == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert event.member_type == MemberType.USER
        assert event.role == WorkspaceRole.MEMBER
        assert event.occurred_at == occurred_at

    def test_creates_with_group_member_type(self):
        """Test that WorkspaceMemberAdded supports group grants."""
        occurred_at = datetime.now(UTC)

        event = WorkspaceMemberAdded(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.GROUP,
            role=WorkspaceRole.EDITOR,
            occurred_at=occurred_at,
        )

        assert event.member_type == MemberType.GROUP
        assert event.role == WorkspaceRole.EDITOR

    def test_is_immutable(self):
        """Test that WorkspaceMemberAdded is immutable (frozen dataclass)."""
        event = WorkspaceMemberAdded(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
            occurred_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            event.workspace_id = "different"  # type: ignore[misc]

    def test_equality_based_on_values(self):
        """Test that two events with same values are equal."""
        occurred_at = datetime.now(UTC)

        event1 = WorkspaceMemberAdded(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.ADMIN,
            occurred_at=occurred_at,
        )
        event2 = WorkspaceMemberAdded(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.ADMIN,
            occurred_at=occurred_at,
        )

        assert event1 == event2

    def test_hashable(self):
        """Test that WorkspaceMemberAdded is hashable (can be used in sets/dicts)."""
        event = WorkspaceMemberAdded(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
            occurred_at=datetime.now(UTC),
        )

        event_set = {event}
        assert len(event_set) == 1

    def test_role_is_workspace_role_enum(self):
        """Test that role uses the WorkspaceRole enum."""
        event = WorkspaceMemberAdded(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.ADMIN,
            occurred_at=datetime.now(UTC),
        )

        assert isinstance(event.role, WorkspaceRole)

    def test_member_type_is_member_type_enum(self):
        """Test that member_type uses the MemberType enum."""
        event = WorkspaceMemberAdded(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
            occurred_at=datetime.now(UTC),
        )

        assert isinstance(event.member_type, MemberType)


class TestWorkspaceMemberRemoved:
    """Tests for WorkspaceMemberRemoved domain event."""

    def test_creates_with_required_fields(self):
        """Test that WorkspaceMemberRemoved can be created with required fields."""
        occurred_at = datetime.now(UTC)

        event = WorkspaceMemberRemoved(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
            occurred_at=occurred_at,
        )

        assert event.workspace_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.member_id == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert event.member_type == MemberType.USER
        assert event.role == WorkspaceRole.MEMBER
        assert event.occurred_at == occurred_at

    def test_creates_with_group_member_type(self):
        """Test that WorkspaceMemberRemoved supports group grants."""
        event = WorkspaceMemberRemoved(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.GROUP,
            role=WorkspaceRole.EDITOR,
            occurred_at=datetime.now(UTC),
        )

        assert event.member_type == MemberType.GROUP

    def test_is_immutable(self):
        """Test that WorkspaceMemberRemoved is immutable (frozen dataclass)."""
        event = WorkspaceMemberRemoved(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
            occurred_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            event.member_id = "different"  # type: ignore[misc]

    def test_equality_based_on_values(self):
        """Test that two events with same values are equal."""
        occurred_at = datetime.now(UTC)

        event1 = WorkspaceMemberRemoved(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.ADMIN,
            occurred_at=occurred_at,
        )
        event2 = WorkspaceMemberRemoved(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.ADMIN,
            occurred_at=occurred_at,
        )

        assert event1 == event2

    def test_hashable(self):
        """Test that WorkspaceMemberRemoved is hashable."""
        event = WorkspaceMemberRemoved(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
            occurred_at=datetime.now(UTC),
        )

        event_set = {event}
        assert len(event_set) == 1


class TestWorkspaceMemberRoleChanged:
    """Tests for WorkspaceMemberRoleChanged domain event."""

    def test_creates_with_required_fields(self):
        """Test that WorkspaceMemberRoleChanged can be created with required fields."""
        occurred_at = datetime.now(UTC)

        event = WorkspaceMemberRoleChanged(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            old_role=WorkspaceRole.MEMBER,
            new_role=WorkspaceRole.ADMIN,
            occurred_at=occurred_at,
        )

        assert event.workspace_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert event.member_id == "01ARZCX0P0HZGQP3MZXQQ0NNWW"
        assert event.member_type == MemberType.USER
        assert event.old_role == WorkspaceRole.MEMBER
        assert event.new_role == WorkspaceRole.ADMIN
        assert event.occurred_at == occurred_at

    def test_creates_with_group_member_type(self):
        """Test that WorkspaceMemberRoleChanged supports group grants."""
        event = WorkspaceMemberRoleChanged(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.GROUP,
            old_role=WorkspaceRole.MEMBER,
            new_role=WorkspaceRole.EDITOR,
            occurred_at=datetime.now(UTC),
        )

        assert event.member_type == MemberType.GROUP

    def test_roles_are_workspace_role_enum(self):
        """Test that both roles use the WorkspaceRole enum."""
        event = WorkspaceMemberRoleChanged(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            old_role=WorkspaceRole.MEMBER,
            new_role=WorkspaceRole.ADMIN,
            occurred_at=datetime.now(UTC),
        )

        assert isinstance(event.old_role, WorkspaceRole)
        assert isinstance(event.new_role, WorkspaceRole)

    def test_is_immutable(self):
        """Test that WorkspaceMemberRoleChanged is immutable (frozen dataclass)."""
        event = WorkspaceMemberRoleChanged(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            old_role=WorkspaceRole.MEMBER,
            new_role=WorkspaceRole.ADMIN,
            occurred_at=datetime.now(UTC),
        )

        with pytest.raises(FrozenInstanceError):
            event.new_role = WorkspaceRole.MEMBER  # type: ignore[misc]

    def test_equality_based_on_all_values(self):
        """Test that two events with same values are equal."""
        occurred_at = datetime.now(UTC)

        event1 = WorkspaceMemberRoleChanged(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            old_role=WorkspaceRole.MEMBER,
            new_role=WorkspaceRole.ADMIN,
            occurred_at=occurred_at,
        )
        event2 = WorkspaceMemberRoleChanged(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            old_role=WorkspaceRole.MEMBER,
            new_role=WorkspaceRole.ADMIN,
            occurred_at=occurred_at,
        )

        assert event1 == event2

    def test_hashable(self):
        """Test that WorkspaceMemberRoleChanged is hashable."""
        event = WorkspaceMemberRoleChanged(
            workspace_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            member_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            member_type=MemberType.USER,
            old_role=WorkspaceRole.MEMBER,
            new_role=WorkspaceRole.ADMIN,
            occurred_at=datetime.now(UTC),
        )

        event_set = {event}
        assert len(event_set) == 1

    def test_supports_all_workspace_roles(self):
        """Test that all three workspace roles can be used."""
        occurred_at = datetime.now(UTC)

        # Test MEMBER -> EDITOR
        event1 = WorkspaceMemberRoleChanged(
            workspace_id="ws1",
            member_id="user1",
            member_type=MemberType.USER,
            old_role=WorkspaceRole.MEMBER,
            new_role=WorkspaceRole.EDITOR,
            occurred_at=occurred_at,
        )
        assert event1.old_role == WorkspaceRole.MEMBER
        assert event1.new_role == WorkspaceRole.EDITOR

        # Test EDITOR -> ADMIN
        event2 = WorkspaceMemberRoleChanged(
            workspace_id="ws1",
            member_id="user1",
            member_type=MemberType.USER,
            old_role=WorkspaceRole.EDITOR,
            new_role=WorkspaceRole.ADMIN,
            occurred_at=occurred_at,
        )
        assert event2.old_role == WorkspaceRole.EDITOR
        assert event2.new_role == WorkspaceRole.ADMIN
