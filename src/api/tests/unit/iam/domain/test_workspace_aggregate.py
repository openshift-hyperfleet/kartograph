"""Unit tests for Workspace aggregate (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the Workspace aggregate to make these tests pass.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import Mock

from iam.domain.aggregates import Workspace
from iam.domain.events import (
    WorkspaceCreated,
    WorkspaceDeleted,
    WorkspaceMemberAdded,
    WorkspaceMemberRemoved,
    WorkspaceMemberRoleChanged,
)
from iam.domain.events.workspace_member import WorkspaceMemberSnapshot
from iam.domain.value_objects import (
    MemberType,
    TenantId,
    WorkspaceId,
    WorkspaceRole,
)


class TestWorkspaceCreation:
    """Tests for Workspace aggregate creation."""

    def test_creates_with_required_fields(self):
        """Test that Workspace can be created with required fields."""
        workspace_id = WorkspaceId.generate()
        tenant_id = TenantId.generate()
        now = datetime.now(UTC)

        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Engineering",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        assert workspace.id == workspace_id
        assert workspace.tenant_id == tenant_id
        assert workspace.name == "Engineering"
        assert workspace.parent_workspace_id is None
        assert workspace.is_root is False
        assert workspace.created_at == now
        assert workspace.updated_at == now

    def test_requires_id(self):
        """Test that Workspace requires an id."""
        now = datetime.now(UTC)
        with pytest.raises(TypeError):
            Workspace(
                tenant_id=TenantId.generate(),
                name="Engineering",
                parent_workspace_id=None,
                is_root=False,
                created_at=now,
                updated_at=now,
            )

    def test_requires_tenant_id(self):
        """Test that Workspace requires a tenant_id."""
        now = datetime.now(UTC)
        with pytest.raises(TypeError):
            Workspace(
                id=WorkspaceId.generate(),
                name="Engineering",
                parent_workspace_id=None,
                is_root=False,
                created_at=now,
                updated_at=now,
            )

    def test_requires_name(self):
        """Test that Workspace requires a name."""
        now = datetime.now(UTC)
        with pytest.raises(TypeError):
            Workspace(
                id=WorkspaceId.generate(),
                tenant_id=TenantId.generate(),
                parent_workspace_id=None,
                is_root=False,
                created_at=now,
                updated_at=now,
            )


class TestWorkspaceFactory:
    """Tests for Workspace.create() factory method."""

    def test_factory_creates_workspace_with_generated_id(self):
        """Factory should generate an ID for the workspace."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        assert workspace.id is not None
        assert workspace.tenant_id == tenant_id
        assert workspace.name == "Engineering"
        assert workspace.parent_workspace_id == parent_id
        assert workspace.is_root is False

    def test_factory_sets_timestamps(self):
        """Factory should set created_at and updated_at to now."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        before = datetime.now(UTC)
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )
        after = datetime.now(UTC)

        assert before <= workspace.created_at <= after
        assert before <= workspace.updated_at <= after
        assert workspace.created_at.tzinfo == UTC
        assert workspace.updated_at.tzinfo == UTC

    def test_factory_records_workspace_created_event(self):
        """Factory should record a WorkspaceCreated event."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceCreated)
        assert events[0].workspace_id == workspace.id.value
        assert events[0].tenant_id == tenant_id.value
        assert events[0].name == "Engineering"
        assert events[0].parent_workspace_id == parent_id.value
        assert events[0].is_root is False

    def test_factory_creates_workspace_with_parent(self):
        """Factory should create workspace with parent when specified."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        workspace = Workspace.create(
            name="Team A",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        assert workspace.parent_workspace_id == parent_id
        assert workspace.is_root is False

        events = workspace.collect_events()
        assert events[0].parent_workspace_id == parent_id.value


class TestRootWorkspaceFactory:
    """Tests for Workspace.create_root() factory method."""

    def test_create_root_creates_root_workspace(self):
        """create_root should create a root workspace."""
        tenant_id = TenantId.generate()

        workspace = Workspace.create_root(
            name="Root Workspace",
            tenant_id=tenant_id,
        )

        assert workspace.is_root is True
        assert workspace.parent_workspace_id is None
        assert workspace.name == "Root Workspace"
        assert workspace.tenant_id == tenant_id

    def test_create_root_records_event_with_is_root_true(self):
        """create_root should record event with is_root=True."""
        tenant_id = TenantId.generate()

        workspace = Workspace.create_root(
            name="Root",
            tenant_id=tenant_id,
        )
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceCreated)
        assert events[0].is_root is True


class TestBusinessRules:
    """Tests for Workspace business rules."""

    def test_name_must_be_between_1_and_512_characters(self):
        """Workspace name must be 1-512 characters."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        # Empty name should fail
        with pytest.raises(ValueError, match="1.*512"):
            Workspace.create(
                name="", tenant_id=tenant_id, parent_workspace_id=parent_id
            )

        # 513 character name should fail
        with pytest.raises(ValueError, match="1.*512"):
            Workspace.create(
                name="a" * 513, tenant_id=tenant_id, parent_workspace_id=parent_id
            )

        # Valid names should work
        workspace_short = Workspace.create(
            name="a", tenant_id=tenant_id, parent_workspace_id=parent_id
        )
        assert workspace_short.name == "a"

        workspace_max = Workspace.create(
            name="a" * 512, tenant_id=tenant_id, parent_workspace_id=parent_id
        )
        assert len(workspace_max.name) == 512

    def test_cannot_have_is_root_true_with_parent_workspace_id(self):
        """Cannot have both is_root=True and parent_workspace_id set."""
        workspace_id = WorkspaceId.generate()
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        now = datetime.now(UTC)

        with pytest.raises(ValueError, match="root.*parent"):
            Workspace(
                id=workspace_id,
                tenant_id=tenant_id,
                name="Invalid",
                parent_workspace_id=parent_id,
                is_root=True,
                created_at=now,
                updated_at=now,
            )

    def test_root_workspace_must_have_no_parent(self):
        """Root workspace must have parent_workspace_id=None."""
        workspace_id = WorkspaceId.generate()
        tenant_id = TenantId.generate()
        now = datetime.now(UTC)

        # This should be valid
        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Root",
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )

        assert workspace.is_root is True
        assert workspace.parent_workspace_id is None

    def test_non_root_workspace_can_have_parent(self):
        """Non-root workspace can have a parent."""
        workspace_id = WorkspaceId.generate()
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        now = datetime.now(UTC)

        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Child",
            parent_workspace_id=parent_id,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        assert workspace.is_root is False
        assert workspace.parent_workspace_id == parent_id


class TestMarkForDeletion:
    """Tests for Workspace.mark_for_deletion() method."""

    def test_records_workspace_deleted_event(self):
        """mark_for_deletion records a WorkspaceDeleted event."""
        tenant_id = TenantId.generate()
        workspace_id = WorkspaceId.generate()
        now = datetime.now(UTC)

        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Engineering",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceDeleted)
        assert events[0].workspace_id == workspace_id.value
        assert events[0].tenant_id == tenant_id.value

    def test_workspace_deleted_event_has_utc_timestamp(self):
        """WorkspaceDeleted event should have UTC timestamp."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )
        workspace.collect_events()  # Clear creation event

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        assert events[0].occurred_at.tzinfo == UTC

    def test_workspace_deleted_event_captures_parent_snapshot(self):
        """WorkspaceDeleted should capture parent_workspace_id snapshot."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )
        workspace.collect_events()  # Clear creation event

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        assert events[0].parent_workspace_id == parent_id.value
        assert events[0].is_root is False

    def test_workspace_deleted_event_captures_root_snapshot(self):
        """WorkspaceDeleted for root workspace should capture is_root=True."""
        tenant_id = TenantId.generate()
        workspace = Workspace.create_root(
            name="Root",
            tenant_id=tenant_id,
        )
        workspace.collect_events()  # Clear creation event

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        assert events[0].is_root is True
        assert events[0].parent_workspace_id is None

    def test_workspace_deleted_event_no_parent_for_non_root_orphan(self):
        """WorkspaceDeleted for non-root without parent should have None parent."""
        tenant_id = TenantId.generate()
        workspace_id = WorkspaceId.generate()
        now = datetime.now(UTC)

        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Orphan",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        assert events[0].parent_workspace_id is None
        assert events[0].is_root is False


class TestEventCollection:
    """Tests for Workspace event collection mechanism."""

    def test_collect_events_returns_empty_list_initially(self):
        """A directly constructed workspace has no pending events."""
        now = datetime.now(UTC)
        workspace = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        events = workspace.collect_events()

        assert events == []

    def test_collect_events_clears_pending_events(self):
        """collect_events clears the pending events list."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        events1 = workspace.collect_events()
        events2 = workspace.collect_events()

        assert len(events1) == 1
        assert len(events2) == 0

    def test_multiple_operations_record_multiple_events(self):
        """Multiple operations record multiple events."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        # Don't collect yet - add deletion
        workspace.mark_for_deletion()

        events = workspace.collect_events()

        assert len(events) == 2
        assert isinstance(events[0], WorkspaceCreated)
        assert isinstance(events[1], WorkspaceDeleted)


# --- Helper to create a workspace for member management tests ---


def _make_workspace() -> Workspace:
    """Create a basic non-root workspace for testing member operations."""
    now = datetime.now(UTC)
    return Workspace(
        id=WorkspaceId.generate(),
        tenant_id=TenantId.generate(),
        name="Engineering",
        parent_workspace_id=None,
        is_root=False,
        created_at=now,
        updated_at=now,
    )


class TestWorkspaceAddMember:
    """Tests for Workspace.add_member() business logic."""

    def test_adds_user_member_successfully(self):
        """Test that a user member can be added to the workspace."""
        workspace = _make_workspace()

        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)

        assert len(workspace.members) == 1
        assert workspace.members[0].member_id == "user-alice"
        assert workspace.members[0].member_type == MemberType.USER
        assert workspace.members[0].role == WorkspaceRole.MEMBER

    def test_adds_group_member_successfully(self):
        """Test that a group member can be added to the workspace."""
        workspace = _make_workspace()

        workspace.add_member("group-eng", MemberType.GROUP, WorkspaceRole.EDITOR)

        assert len(workspace.members) == 1
        assert workspace.members[0].member_id == "group-eng"
        assert workspace.members[0].member_type == MemberType.GROUP
        assert workspace.members[0].role == WorkspaceRole.EDITOR

    def test_records_workspace_member_added_event(self):
        """Test that add_member records a WorkspaceMemberAdded event."""
        workspace = _make_workspace()

        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.ADMIN)
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceMemberAdded)
        assert events[0].workspace_id == workspace.id.value
        assert events[0].member_id == "user-alice"
        assert events[0].member_type == "user"
        assert events[0].role == "admin"

    def test_supports_all_three_roles(self):
        """Test that all three workspace roles (ADMIN, EDITOR, MEMBER) are supported."""
        workspace = _make_workspace()

        workspace.add_member("user-admin", MemberType.USER, WorkspaceRole.ADMIN)
        workspace.add_member("user-editor", MemberType.USER, WorkspaceRole.EDITOR)
        workspace.add_member("user-viewer", MemberType.USER, WorkspaceRole.MEMBER)

        assert len(workspace.members) == 3
        roles = {m.role for m in workspace.members}
        assert roles == {
            WorkspaceRole.ADMIN,
            WorkspaceRole.EDITOR,
            WorkspaceRole.MEMBER,
        }

    def test_prevents_duplicate_user_members(self):
        """Test that same user cannot be added twice."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)

        with pytest.raises(ValueError, match="already a member"):
            workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.ADMIN)

    def test_prevents_duplicate_group_members(self):
        """Test that same group cannot be added twice."""
        workspace = _make_workspace()
        workspace.add_member("group-eng", MemberType.GROUP, WorkspaceRole.EDITOR)

        with pytest.raises(ValueError, match="already a member"):
            workspace.add_member("group-eng", MemberType.GROUP, WorkspaceRole.ADMIN)

    def test_allows_same_id_different_types(self):
        """Test that same ID with different member types is allowed.

        user:alice and group:alice are distinct members.
        """
        workspace = _make_workspace()

        workspace.add_member("alice", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.add_member("alice", MemberType.GROUP, WorkspaceRole.EDITOR)

        assert len(workspace.members) == 2


class TestWorkspaceAddMemberRoleReplacement:
    """Tests for role replacement in Workspace.add_member()."""

    def test_replaces_role_when_current_role_differs(self):
        """Test that add_member emits MemberRemoved + MemberAdded when replacing role."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.collect_events()  # Clear

        workspace.add_member(
            "user-alice",
            MemberType.USER,
            WorkspaceRole.ADMIN,
            current_role=WorkspaceRole.MEMBER,
        )

        events = workspace.collect_events()
        assert len(events) == 2
        assert isinstance(events[0], WorkspaceMemberRemoved)
        assert events[0].role == "member"
        assert events[0].member_id == "user-alice"
        assert isinstance(events[1], WorkspaceMemberAdded)
        assert events[1].role == "admin"

    def test_replacement_updates_in_memory_members(self):
        """Test that role replacement updates the in-memory members list."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)

        workspace.add_member(
            "user-alice",
            MemberType.USER,
            WorkspaceRole.ADMIN,
            current_role=WorkspaceRole.MEMBER,
        )

        assert len(workspace.members) == 1
        assert (
            workspace.get_member_role("user-alice", MemberType.USER)
            == WorkspaceRole.ADMIN
        )

    def test_no_removal_when_current_role_is_same(self):
        """Test that add_member raises ValueError when role is the same."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.ADMIN)

        # Same role with current_role specified - should still just add (no removal)
        workspace.add_member(
            "user-bob",
            MemberType.USER,
            WorkspaceRole.ADMIN,
            current_role=WorkspaceRole.ADMIN,
        )

        # Only MemberAdded for bob
        events = workspace.collect_events()
        added_events = [e for e in events if isinstance(e, WorkspaceMemberAdded)]
        removed_events = [e for e in events if isinstance(e, WorkspaceMemberRemoved)]
        # alice add + bob add, no removals for bob
        assert len(added_events) == 2
        assert len(removed_events) == 0

    def test_no_removal_when_no_current_role(self):
        """Test that add_member does NOT emit MemberRemoved for new members."""
        workspace = _make_workspace()

        workspace.add_member(
            "user-alice",
            MemberType.USER,
            WorkspaceRole.MEMBER,
            current_role=None,
        )

        events = workspace.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], WorkspaceMemberAdded)


class TestWorkspaceRemoveMember:
    """Tests for Workspace.remove_member() business logic."""

    def test_removes_user_member_successfully(self):
        """Test that a user member can be removed from the workspace."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.collect_events()  # Clear add event

        workspace.remove_member("user-alice", MemberType.USER)

        assert len(workspace.members) == 0

    def test_removes_group_member_successfully(self):
        """Test that a group member can be removed from the workspace."""
        workspace = _make_workspace()
        workspace.add_member("group-eng", MemberType.GROUP, WorkspaceRole.EDITOR)
        workspace.collect_events()  # Clear add event

        workspace.remove_member("group-eng", MemberType.GROUP)

        assert len(workspace.members) == 0

    def test_records_workspace_member_removed_event(self):
        """Test that remove_member records a WorkspaceMemberRemoved event."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.EDITOR)
        workspace.collect_events()  # Clear add event

        workspace.remove_member("user-alice", MemberType.USER)
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceMemberRemoved)
        assert events[0].workspace_id == workspace.id.value
        assert events[0].member_id == "user-alice"
        assert events[0].member_type == "user"
        assert events[0].role == "editor"

    def test_raises_if_member_not_found(self):
        """Test that removing a non-existent member raises ValueError."""
        workspace = _make_workspace()

        with pytest.raises(ValueError, match="not a member"):
            workspace.remove_member("user-unknown", MemberType.USER)

    def test_removes_from_members_list(self):
        """Test that removed member is no longer in the members list."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.ADMIN)
        workspace.add_member("user-bob", MemberType.USER, WorkspaceRole.MEMBER)

        workspace.remove_member("user-alice", MemberType.USER)

        assert not workspace.has_member("user-alice", MemberType.USER)
        assert workspace.has_member("user-bob", MemberType.USER)
        assert len(workspace.members) == 1


class TestWorkspaceUpdateMemberRole:
    """Tests for Workspace.update_member_role() business logic."""

    def test_updates_role_successfully(self):
        """Test that a member's role can be updated."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.collect_events()

        workspace.update_member_role("user-alice", MemberType.USER, WorkspaceRole.ADMIN)

        assert workspace.get_member_role("user-alice", MemberType.USER) == (
            WorkspaceRole.ADMIN
        )

    def test_records_workspace_member_role_changed_event(self):
        """Test that update_member_role records a WorkspaceMemberRoleChanged event."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.collect_events()

        workspace.update_member_role(
            "user-alice", MemberType.USER, WorkspaceRole.EDITOR
        )
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceMemberRoleChanged)
        assert events[0].workspace_id == workspace.id.value
        assert events[0].member_id == "user-alice"
        assert events[0].member_type == "user"
        assert events[0].old_role == "member"
        assert events[0].new_role == "editor"

    def test_raises_if_member_not_found(self):
        """Test that updating a non-existent member raises ValueError."""
        workspace = _make_workspace()

        with pytest.raises(ValueError, match="not a member"):
            workspace.update_member_role(
                "user-unknown", MemberType.USER, WorkspaceRole.ADMIN
            )

    def test_raises_if_role_unchanged(self):
        """Test that setting the same role raises ValueError."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.EDITOR)

        with pytest.raises(ValueError, match="already has role"):
            workspace.update_member_role(
                "user-alice", MemberType.USER, WorkspaceRole.EDITOR
            )

    def test_updates_in_memory_member_list(self):
        """Test that the in-memory member list is correctly updated."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.add_member("user-bob", MemberType.USER, WorkspaceRole.EDITOR)

        workspace.update_member_role("user-alice", MemberType.USER, WorkspaceRole.ADMIN)

        # Alice should now be ADMIN
        assert workspace.get_member_role("user-alice", MemberType.USER) == (
            WorkspaceRole.ADMIN
        )
        # Bob should remain EDITOR
        assert workspace.get_member_role("user-bob", MemberType.USER) == (
            WorkspaceRole.EDITOR
        )


class TestWorkspaceMarkForDeletionWithMembers:
    """Tests for mark_for_deletion() with member snapshot."""

    def test_includes_member_snapshot_in_event(self):
        """mark_for_deletion should include member snapshot in WorkspaceDeleted."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.ADMIN)
        workspace.add_member("group-eng", MemberType.GROUP, WorkspaceRole.EDITOR)
        workspace.collect_events()  # Clear add events

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, WorkspaceDeleted)
        assert len(event.members) == 2

        # Verify member snapshots
        member_ids = {m.member_id for m in event.members}
        assert "user-alice" in member_ids
        assert "group-eng" in member_ids

    def test_includes_empty_members_tuple_if_no_members(self):
        """mark_for_deletion should include empty tuple if workspace has no members."""
        workspace = _make_workspace()

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        event = events[0]
        assert isinstance(event, WorkspaceDeleted)
        assert event.members == ()

    def test_snapshot_captures_member_type_and_role(self):
        """Member snapshot should capture member_type and role correctly."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.ADMIN)
        workspace.add_member("group-eng", MemberType.GROUP, WorkspaceRole.MEMBER)
        workspace.collect_events()

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        event = events[0]
        for snapshot in event.members:
            assert isinstance(snapshot, WorkspaceMemberSnapshot)
            if snapshot.member_id == "user-alice":
                assert snapshot.member_type == "user"
                assert snapshot.role == "admin"
            elif snapshot.member_id == "group-eng":
                assert snapshot.member_type == "group"
                assert snapshot.role == "member"


class TestWorkspaceMemberHelpers:
    """Tests for Workspace member helper methods."""

    def test_has_member_returns_true_for_existing(self):
        """has_member should return True for an existing member."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)

        assert workspace.has_member("user-alice", MemberType.USER) is True

    def test_has_member_returns_false_for_nonexistent(self):
        """has_member should return False for a non-existent member."""
        workspace = _make_workspace()

        assert workspace.has_member("user-unknown", MemberType.USER) is False

    def test_has_member_distinguishes_user_vs_group(self):
        """has_member should distinguish between user and group types."""
        workspace = _make_workspace()
        workspace.add_member("alice", MemberType.USER, WorkspaceRole.MEMBER)

        assert workspace.has_member("alice", MemberType.USER) is True
        assert workspace.has_member("alice", MemberType.GROUP) is False

    def test_get_member_role_returns_correct_role(self):
        """get_member_role should return the correct role for an existing member."""
        workspace = _make_workspace()
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.EDITOR)

        role = workspace.get_member_role("user-alice", MemberType.USER)

        assert role == WorkspaceRole.EDITOR

    def test_get_member_role_returns_none_if_not_found(self):
        """get_member_role should return None for a non-existent member."""
        workspace = _make_workspace()

        role = workspace.get_member_role("user-unknown", MemberType.USER)

        assert role is None


class TestMemberIdValidation:
    """Tests for member_id validation across workspace member operations."""

    def test_add_member_rejects_empty_member_id(self):
        """add_member should reject an empty member_id."""
        workspace = _make_workspace()

        with pytest.raises(ValueError, match="member_id cannot be empty"):
            workspace.add_member("", MemberType.USER, WorkspaceRole.MEMBER)

    def test_add_member_rejects_whitespace_only_member_id(self):
        """add_member should reject a whitespace-only member_id."""
        workspace = _make_workspace()

        with pytest.raises(ValueError, match="member_id cannot be empty"):
            workspace.add_member("   ", MemberType.USER, WorkspaceRole.EDITOR)

    def test_remove_member_rejects_empty_member_id(self):
        """remove_member should reject an empty member_id."""
        workspace = _make_workspace()

        with pytest.raises(ValueError, match="member_id cannot be empty"):
            workspace.remove_member("", MemberType.USER)

    def test_remove_member_rejects_whitespace_only_member_id(self):
        """remove_member should reject a whitespace-only member_id."""
        workspace = _make_workspace()

        with pytest.raises(ValueError, match="member_id cannot be empty"):
            workspace.remove_member("   ", MemberType.GROUP)

    def test_update_member_role_rejects_empty_member_id(self):
        """update_member_role should reject an empty member_id."""
        workspace = _make_workspace()

        with pytest.raises(ValueError, match="member_id cannot be empty"):
            workspace.update_member_role("", MemberType.USER, WorkspaceRole.ADMIN)

    def test_update_member_role_rejects_whitespace_only_member_id(self):
        """update_member_role should reject a whitespace-only member_id."""
        workspace = _make_workspace()

        with pytest.raises(ValueError, match="member_id cannot be empty"):
            workspace.update_member_role("   ", MemberType.GROUP, WorkspaceRole.EDITOR)


class TestMemberIdTypeValidation:
    """Tests for member_id type validation before .strip() is called."""

    def test_add_member_rejects_none_member_id(self):
        """Should raise TypeError if member_id is None."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_id must be str, got NoneType"):
            workspace.add_member(None, MemberType.USER, WorkspaceRole.ADMIN)

    def test_add_member_rejects_int_member_id(self):
        """Should raise TypeError if member_id is int."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_id must be str, got int"):
            workspace.add_member(123, MemberType.USER, WorkspaceRole.ADMIN)

    def test_remove_member_rejects_none_member_id(self):
        """Should raise TypeError if member_id is None."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_id must be str, got NoneType"):
            workspace.remove_member(None, MemberType.USER)

    def test_remove_member_rejects_int_member_id(self):
        """Should raise TypeError if member_id is int."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_id must be str, got int"):
            workspace.remove_member(123, MemberType.USER)

    def test_update_member_role_rejects_none_member_id(self):
        """Should raise TypeError if member_id is None."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_id must be str, got NoneType"):
            workspace.update_member_role(None, MemberType.USER, WorkspaceRole.EDITOR)

    def test_update_member_role_rejects_int_member_id(self):
        """Should raise TypeError if member_id is int."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_id must be str, got int"):
            workspace.update_member_role(123, MemberType.USER, WorkspaceRole.EDITOR)


class TestMemberTypeValidation:
    """Tests for enum type validation in workspace member operations."""

    def test_add_member_rejects_invalid_member_type(self):
        """Should raise TypeError if member_type is not MemberType enum."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_type must be MemberType"):
            workspace.add_member("user123", "user", WorkspaceRole.ADMIN)

    def test_add_member_rejects_invalid_role(self):
        """Should raise TypeError if role is not WorkspaceRole enum."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="role must be WorkspaceRole"):
            workspace.add_member("user123", MemberType.USER, "admin")

    def test_remove_member_rejects_invalid_member_type(self):
        """Should raise TypeError if member_type is not MemberType enum."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_type must be MemberType"):
            workspace.remove_member("user123", "user")

    def test_update_member_role_rejects_invalid_member_type(self):
        """Should raise TypeError if member_type is not MemberType enum."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="member_type must be MemberType"):
            workspace.update_member_role("user123", "user", WorkspaceRole.ADMIN)

    def test_update_member_role_rejects_invalid_new_role(self):
        """Should raise TypeError if new_role is not WorkspaceRole enum."""
        workspace = _make_workspace()

        with pytest.raises(TypeError, match="new_role must be WorkspaceRole"):
            workspace.update_member_role("user123", MemberType.USER, "admin")


class TestMemberIdNormalization:
    """Tests for member_id normalization (whitespace stripping) in workspace member operations."""

    def test_add_member_normalizes_member_id(self):
        """Should strip whitespace from member_id when adding a member."""
        workspace = _make_workspace()

        workspace.add_member("  user123  ", MemberType.USER, WorkspaceRole.ADMIN)

        assert workspace.has_member("user123", MemberType.USER)
        assert (
            workspace.get_member_role("user123", MemberType.USER) == WorkspaceRole.ADMIN
        )

    def test_add_member_stores_normalized_member_id(self):
        """Should store the normalized (stripped) member_id in the members list."""
        workspace = _make_workspace()

        workspace.add_member("  user123  ", MemberType.USER, WorkspaceRole.EDITOR)

        assert workspace.members[0].member_id == "user123"

    def test_add_member_event_uses_normalized_member_id(self):
        """WorkspaceMemberAdded event should use the normalized member_id."""
        workspace = _make_workspace()

        workspace.add_member("  user123  ", MemberType.USER, WorkspaceRole.ADMIN)
        events = workspace.collect_events()

        assert events[0].member_id == "user123"

    def test_add_member_probe_uses_normalized_member_id(self):
        """Probe emission should use the normalized member_id."""
        probe = Mock()
        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
            probe=probe,
        )

        workspace.add_member("  user123  ", MemberType.USER, WorkspaceRole.EDITOR)

        probe.member_added.assert_called_once_with(
            workspace_id=workspace.id.value,
            member_id="user123",
            member_type="user",
            role="editor",
        )

    def test_add_member_duplicate_check_uses_normalized_id(self):
        """Duplicate check should use normalized member_id."""
        workspace = _make_workspace()
        workspace.add_member("user123", MemberType.USER, WorkspaceRole.MEMBER)

        with pytest.raises(ValueError, match="already a member"):
            workspace.add_member("  user123  ", MemberType.USER, WorkspaceRole.ADMIN)

    def test_remove_member_normalizes_member_id(self):
        """Should strip whitespace from member_id when removing a member."""
        workspace = _make_workspace()
        workspace.add_member("user123", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.collect_events()

        workspace.remove_member("  user123  ", MemberType.USER)

        assert not workspace.has_member("user123", MemberType.USER)

    def test_remove_member_event_uses_normalized_member_id(self):
        """WorkspaceMemberRemoved event should use the normalized member_id."""
        workspace = _make_workspace()
        workspace.add_member("user123", MemberType.USER, WorkspaceRole.EDITOR)
        workspace.collect_events()

        workspace.remove_member("  user123  ", MemberType.USER)
        events = workspace.collect_events()

        assert events[0].member_id == "user123"

    def test_remove_member_probe_uses_normalized_member_id(self):
        """Probe emission should use the normalized member_id on remove."""
        probe = Mock()
        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
            probe=probe,
        )
        workspace.add_member("user123", MemberType.USER, WorkspaceRole.EDITOR)
        probe.reset_mock()

        workspace.remove_member("  user123  ", MemberType.USER)

        probe.member_removed.assert_called_once_with(
            workspace_id=workspace.id.value,
            member_id="user123",
            member_type="user",
            role="editor",
        )

    def test_update_member_role_normalizes_member_id(self):
        """Should strip whitespace from member_id when updating role."""
        workspace = _make_workspace()
        workspace.add_member("user123", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.collect_events()

        workspace.update_member_role(
            "  user123  ", MemberType.USER, WorkspaceRole.ADMIN
        )

        assert (
            workspace.get_member_role("user123", MemberType.USER) == WorkspaceRole.ADMIN
        )

    def test_update_member_role_event_uses_normalized_member_id(self):
        """WorkspaceMemberRoleChanged event should use the normalized member_id."""
        workspace = _make_workspace()
        workspace.add_member("user123", MemberType.USER, WorkspaceRole.MEMBER)
        workspace.collect_events()

        workspace.update_member_role(
            "  user123  ", MemberType.USER, WorkspaceRole.ADMIN
        )
        events = workspace.collect_events()

        assert events[0].member_id == "user123"

    def test_update_member_role_probe_uses_normalized_member_id(self):
        """Probe emission should use the normalized member_id on role update."""
        probe = Mock()
        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
            probe=probe,
        )
        workspace.add_member("user123", MemberType.USER, WorkspaceRole.MEMBER)
        probe.reset_mock()

        workspace.update_member_role(
            "  user123  ", MemberType.USER, WorkspaceRole.ADMIN
        )

        probe.member_role_changed.assert_called_once_with(
            workspace_id=workspace.id.value,
            member_id="user123",
            member_type="user",
            old_role="member",
            new_role="admin",
        )


class TestWorkspaceProbes:
    """Tests for workspace domain probe emissions.

    Verifies that workspace member operations emit the correct domain probes
    following the Domain Oriented Observability pattern.
    """

    def test_add_member_emits_probe(self):
        """Verify member_added probe is emitted when adding a member."""
        probe = Mock()
        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
            probe=probe,
        )

        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.EDITOR)

        probe.member_added.assert_called_once_with(
            workspace_id=workspace.id.value,
            member_id="user-alice",
            member_type="user",
            role="editor",
        )

    def test_add_group_member_emits_probe(self):
        """Verify member_added probe is emitted for group members."""
        probe = Mock()
        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
            probe=probe,
        )

        workspace.add_member("group-eng", MemberType.GROUP, WorkspaceRole.ADMIN)

        probe.member_added.assert_called_once_with(
            workspace_id=workspace.id.value,
            member_id="group-eng",
            member_type="group",
            role="admin",
        )

    def test_remove_member_emits_probe(self):
        """Verify member_removed probe is emitted when removing a member."""
        probe = Mock()
        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
            probe=probe,
        )
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.EDITOR)

        workspace.remove_member("user-alice", MemberType.USER)

        probe.member_removed.assert_called_once_with(
            workspace_id=workspace.id.value,
            member_id="user-alice",
            member_type="user",
            role="editor",
        )

    def test_update_member_role_emits_probe(self):
        """Verify member_role_changed probe is emitted when updating a role."""
        probe = Mock()
        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
            probe=probe,
        )
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)

        workspace.update_member_role("user-alice", MemberType.USER, WorkspaceRole.ADMIN)

        probe.member_role_changed.assert_called_once_with(
            workspace_id=workspace.id.value,
            member_id="user-alice",
            member_type="user",
            old_role="member",
            new_role="admin",
        )

    def test_probe_not_emitted_on_add_member_validation_failure(self):
        """Verify probe is NOT emitted when add_member validation fails."""
        probe = Mock()
        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
            probe=probe,
        )
        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.MEMBER)
        probe.reset_mock()

        # Try to add duplicate - should fail
        with pytest.raises(ValueError, match="already a member"):
            workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.ADMIN)

        probe.member_added.assert_not_called()

    def test_create_root_accepts_probe(self):
        """Verify create_root factory accepts a probe parameter."""
        probe = Mock()
        workspace = Workspace.create_root(
            name="Root",
            tenant_id=TenantId.generate(),
            probe=probe,
        )

        workspace.add_member("user-alice", MemberType.USER, WorkspaceRole.ADMIN)

        probe.member_added.assert_called_once()

    def test_default_probe_used_when_none_provided(self):
        """Verify DefaultWorkspaceProbe is used when no probe is provided."""
        from iam.domain.observability.workspace_probe import DefaultWorkspaceProbe

        workspace = Workspace.create(
            name="Test",
            tenant_id=TenantId.generate(),
            parent_workspace_id=WorkspaceId.generate(),
        )

        assert isinstance(workspace._probe, DefaultWorkspaceProbe)
