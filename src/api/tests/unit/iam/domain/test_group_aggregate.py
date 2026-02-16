"""Unit tests for Group aggregate (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the Group aggregate to make these tests pass.
"""

import pytest

from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, GroupRole, TenantId, UserId


class TestGroupCreation:
    """Tests for Group aggregate creation."""

    def test_creates_with_required_fields(self):
        """Test that Group can be created with required fields."""
        group_id = GroupId.generate()
        tenant_id = TenantId.generate()

        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering",
        )

        assert group.id == group_id
        assert group.tenant_id == tenant_id
        assert group.name == "Engineering"
        assert group.members == []

    def test_requires_id(self):
        """Test that Group requires an id."""
        with pytest.raises(TypeError):
            Group(
                tenant_id=TenantId.generate(),
                name="Engineering",
            )

    def test_requires_tenant_id(self):
        """Test that Group requires a tenant_id."""
        with pytest.raises(TypeError):
            Group(
                id=GroupId.generate(),
                name="Engineering",
            )

    def test_requires_name(self):
        """Test that Group requires a name."""
        with pytest.raises(TypeError):
            Group(
                id=GroupId.generate(),
                tenant_id=TenantId.generate(),
            )


class TestGroupFactory:
    """Tests for Group.create() factory method."""

    def test_factory_creates_group_with_generated_id(self):
        """Factory should generate an ID for the group."""
        tenant_id = TenantId.generate()

        group = Group.create(name="Engineering", tenant_id=tenant_id)

        assert group.id is not None
        assert group.tenant_id == tenant_id
        assert group.name == "Engineering"
        assert group.members == []

    def test_factory_records_group_created_event(self):
        """Factory should record a GroupCreated event."""
        from iam.domain.events import GroupCreated

        tenant_id = TenantId.generate()

        group = Group.create(name="Engineering", tenant_id=tenant_id)
        events = group.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], GroupCreated)
        assert events[0].group_id == group.id.value
        assert events[0].tenant_id == tenant_id.value


class TestAddMember:
    """Tests for Group.add_member() business logic."""

    def test_adds_member_with_role(self):
        """Test that member can be added with a role."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        group.add_member(user_id, GroupRole.MEMBER)

        assert len(group.members) == 1
        assert group.members[0].user_id == user_id
        assert group.members[0].role == GroupRole.MEMBER

    def test_adds_admin(self):
        """Test that admin can be added."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin_id = UserId.generate()

        group.add_member(admin_id, GroupRole.ADMIN)

        assert group.members[0].role == GroupRole.ADMIN

    def test_adds_multiple_members(self):
        """Test that multiple members can be added."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        alice = UserId.generate()
        bob = UserId.generate()

        group.add_member(alice, GroupRole.ADMIN)
        group.add_member(bob, GroupRole.MEMBER)

        assert len(group.members) == 2

    def test_prevents_duplicate_members(self):
        """Test that same user cannot be added twice."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        group.add_member(user_id, GroupRole.MEMBER)

        with pytest.raises(ValueError, match="already a member"):
            group.add_member(user_id, GroupRole.ADMIN)


class TestAddMemberRoleReplacement:
    """Tests for role replacement in Group.add_member()."""

    def test_replaces_role_when_current_role_differs(self):
        """Test that add_member emits MemberRemoved + MemberAdded when replacing role."""
        from iam.domain.events import MemberAdded, MemberRemoved

        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, GroupRole.MEMBER)
        group.collect_events()  # Clear

        group.add_member(user_id, GroupRole.ADMIN, current_role=GroupRole.MEMBER)

        events = group.collect_events()
        assert len(events) == 2
        assert isinstance(events[0], MemberRemoved)
        assert events[0].role == GroupRole.MEMBER.value
        assert isinstance(events[1], MemberAdded)
        assert events[1].role == GroupRole.ADMIN.value

    def test_replacement_updates_in_memory_members(self):
        """Test that role replacement updates the in-memory members list."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, GroupRole.MEMBER)

        group.add_member(user_id, GroupRole.ADMIN, current_role=GroupRole.MEMBER)

        assert len(group.members) == 1
        assert group.get_member_role(user_id) == GroupRole.ADMIN

    def test_no_removal_when_current_role_is_same(self):
        """Test that add_member raises ValueError when trying to add with same role."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, GroupRole.ADMIN)

        # Same role with current_role -- should still pass (idempotent add)
        # It won't remove and will re-add (but member already exists in list)
        # Actually, since current_role == role, it falls through to has_member check
        with pytest.raises(ValueError, match="already a member"):
            group.add_member(user_id, GroupRole.ADMIN, current_role=GroupRole.ADMIN)

    def test_no_removal_when_no_current_role(self):
        """Test that add_member does NOT emit MemberRemoved for new members."""
        from iam.domain.events import MemberAdded

        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        group.add_member(user_id, GroupRole.MEMBER, current_role=None)

        events = group.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], MemberAdded)

    def test_prevents_demoting_last_admin_via_role_replacement(self):
        """Test that replacing ADMIN with MEMBER role is blocked when last admin."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin_id = UserId.generate()
        group.add_member(admin_id, GroupRole.ADMIN)

        with pytest.raises(ValueError, match="last admin"):
            group.add_member(admin_id, GroupRole.MEMBER, current_role=GroupRole.ADMIN)

    def test_allows_demoting_admin_via_replacement_when_multiple_admins(self):
        """Test that replacing ADMIN with MEMBER role is allowed when other admins exist."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin1 = UserId.generate()
        admin2 = UserId.generate()
        group.add_member(admin1, GroupRole.ADMIN)
        group.add_member(admin2, GroupRole.ADMIN)

        group.add_member(admin1, GroupRole.MEMBER, current_role=GroupRole.ADMIN)

        assert group.get_member_role(admin1) == GroupRole.MEMBER
        assert group.get_member_role(admin2) == GroupRole.ADMIN


class TestHasMember:
    """Tests for Group.has_member() method."""

    def test_returns_true_when_member_exists(self):
        """Test that has_member returns True for existing member."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, GroupRole.MEMBER)

        assert group.has_member(user_id) is True

    def test_returns_false_when_member_does_not_exist(self):
        """Test that has_member returns False for non-member."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        assert group.has_member(user_id) is False


class TestGetMemberRole:
    """Tests for Group.get_member_role() method."""

    def test_returns_role_for_member(self):
        """Test that get_member_role returns correct role."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, GroupRole.ADMIN)

        role = group.get_member_role(user_id)

        assert role == GroupRole.ADMIN

    def test_returns_none_for_non_member(self):
        """Test that get_member_role returns None for non-member."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        role = group.get_member_role(user_id)

        assert role is None


class TestRemoveMember:
    """Tests for Group.remove_member() business logic."""

    def test_removes_existing_member(self):
        """Test that member can be removed."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin_id = UserId.generate()
        user_id = UserId.generate()
        # Add an admin first so we can remove the regular member
        group.add_member(admin_id, GroupRole.ADMIN)
        group.add_member(user_id, GroupRole.MEMBER)

        group.remove_member(user_id)

        assert len(group.members) == 1
        assert not group.has_member(user_id)

    def test_raises_when_removing_non_member(self):
        """Test that removing non-member raises error."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        with pytest.raises(ValueError, match="not a member"):
            group.remove_member(user_id)

    def test_prevents_removing_last_admin(self):
        """Test that last admin cannot be removed."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin_id = UserId.generate()
        group.add_member(admin_id, GroupRole.ADMIN)

        with pytest.raises(ValueError, match="last admin"):
            group.remove_member(admin_id)

    def test_can_remove_admin_when_multiple_admins_exist(self):
        """Test that admin can be removed if other admins exist."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin1 = UserId.generate()
        admin2 = UserId.generate()
        group.add_member(admin1, GroupRole.ADMIN)
        group.add_member(admin2, GroupRole.ADMIN)

        group.remove_member(admin1)

        assert len(group.members) == 1
        assert group.has_member(admin2)


class TestUpdateMemberRole:
    """Tests for Group.update_member_role() business logic."""

    def test_updates_member_role(self):
        """Test that member role can be updated."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, GroupRole.MEMBER)

        group.update_member_role(user_id, GroupRole.ADMIN)

        assert group.get_member_role(user_id) == GroupRole.ADMIN

    def test_raises_when_updating_non_member(self):
        """Test that updating non-member raises error."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        with pytest.raises(ValueError, match="not a member"):
            group.update_member_role(user_id, GroupRole.ADMIN)

    def test_prevents_demoting_last_admin(self):
        """Test that last admin cannot be demoted."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin_id = UserId.generate()
        group.add_member(admin_id, GroupRole.ADMIN)

        with pytest.raises(ValueError, match="last admin"):
            group.update_member_role(admin_id, GroupRole.MEMBER)

    def test_can_demote_admin_when_multiple_admins_exist(self):
        """Test that admin can be demoted if other admins exist."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin1 = UserId.generate()
        admin2 = UserId.generate()
        group.add_member(admin1, GroupRole.ADMIN)
        group.add_member(admin2, GroupRole.ADMIN)

        group.update_member_role(admin1, GroupRole.MEMBER)

        assert group.get_member_role(admin1) == GroupRole.MEMBER


class TestEventCollection:
    """Tests for Group event collection mechanism.

    The aggregate should record domain events during mutations that can be
    collected and processed by the repository for the outbox pattern.
    """

    def test_collect_events_returns_empty_list_initially(self):
        """Test that a directly constructed group has no pending events."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )

        events = group.collect_events()

        assert events == []

    def test_add_member_records_member_added_event(self):
        """Test that add_member records a MemberAdded event."""
        from iam.domain.events import MemberAdded

        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        group.add_member(user_id, GroupRole.MEMBER)
        events = group.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], MemberAdded)
        assert events[0].group_id == group.id.value
        assert events[0].user_id == user_id.value
        assert events[0].role == GroupRole.MEMBER

    def test_remove_member_records_member_removed_event(self):
        """Test that remove_member records a MemberRemoved event."""
        from iam.domain.events import MemberRemoved

        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin_id = UserId.generate()
        user_id = UserId.generate()
        group.add_member(admin_id, GroupRole.ADMIN)
        group.add_member(user_id, GroupRole.MEMBER)
        group.collect_events()  # Clear creation events

        group.remove_member(user_id)
        events = group.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], MemberRemoved)
        assert events[0].group_id == group.id.value
        assert events[0].user_id == user_id.value
        assert events[0].role == GroupRole.MEMBER

    def test_update_member_role_records_member_role_changed_event(self):
        """Test that update_member_role records a MemberRoleChanged event."""
        from iam.domain.events import MemberRoleChanged

        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        admin_id = UserId.generate()
        user_id = UserId.generate()
        group.add_member(admin_id, GroupRole.ADMIN)
        group.add_member(user_id, GroupRole.MEMBER)
        group.collect_events()  # Clear creation events

        group.update_member_role(user_id, GroupRole.ADMIN)
        events = group.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], MemberRoleChanged)
        assert events[0].group_id == group.id.value
        assert events[0].user_id == user_id.value
        assert events[0].old_role == GroupRole.MEMBER
        assert events[0].new_role == GroupRole.ADMIN

    def test_collect_events_clears_pending_events(self):
        """Test that collect_events clears the pending events list."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, GroupRole.MEMBER)

        # First collection should have events
        events1 = group.collect_events()
        assert len(events1) == 1

        # Second collection should be empty
        events2 = group.collect_events()
        assert events2 == []

    def test_multiple_operations_record_multiple_events(self):
        """Test that multiple operations record multiple events."""
        group = Group(
            id=GroupId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
        )
        user1 = UserId.generate()
        user2 = UserId.generate()
        user3 = UserId.generate()

        group.add_member(user1, GroupRole.ADMIN)
        group.add_member(user2, GroupRole.MEMBER)
        group.add_member(user3, GroupRole.MEMBER)

        events = group.collect_events()

        assert len(events) == 3


class TestMarkForDeletion:
    """Tests for Group.mark_for_deletion() method."""

    def test_records_group_deleted_event(self):
        """Test that mark_for_deletion records a GroupDeleted event."""
        from iam.domain.events import GroupDeleted

        tenant_id = TenantId.generate()
        group = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Engineering",
        )

        group.mark_for_deletion()
        events = group.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], GroupDeleted)
        assert events[0].group_id == group.id.value
        assert events[0].tenant_id == tenant_id.value

    def test_group_deleted_event_includes_member_snapshot(self):
        """Test that GroupDeleted includes all current members."""
        from iam.domain.events import GroupDeleted, MemberSnapshot

        tenant_id = TenantId.generate()
        group = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Engineering",
        )
        admin_id = UserId.generate()
        member_id = UserId.generate()
        group.add_member(admin_id, GroupRole.ADMIN)
        group.add_member(member_id, GroupRole.MEMBER)
        group.collect_events()  # Clear add events

        group.mark_for_deletion()
        events = group.collect_events()

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, GroupDeleted)
        assert len(event.members) == 2

        # Verify member snapshots
        member_ids = {m.user_id for m in event.members}
        assert admin_id.value in member_ids
        assert member_id.value in member_ids

        for snapshot in event.members:
            assert isinstance(snapshot, MemberSnapshot)
            if snapshot.user_id == admin_id.value:
                assert snapshot.role == GroupRole.ADMIN
            else:
                assert snapshot.role == GroupRole.MEMBER
