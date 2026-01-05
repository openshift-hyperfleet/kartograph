"""Unit tests for Group aggregate (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the Group aggregate to make these tests pass.
"""

import pytest

from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, Role, UserId


class TestGroupCreation:
    """Tests for Group aggregate creation."""

    def test_creates_with_required_fields(self):
        """Test that Group can be created with required fields."""
        group_id = GroupId.generate()

        group = Group(
            id=group_id,
            name="Engineering",
        )

        assert group.id == group_id
        assert group.name == "Engineering"
        assert group.members == []

    def test_requires_id(self):
        """Test that Group requires an id."""
        with pytest.raises(TypeError):
            Group(
                name="Engineering",
            )

    def test_requires_name(self):
        """Test that Group requires a name."""
        with pytest.raises(TypeError):
            Group(
                id=GroupId.generate(),
            )


class TestAddMember:
    """Tests for Group.add_member() business logic."""

    def test_adds_member_with_role(self):
        """Test that member can be added with a role."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        group.add_member(user_id, Role.MEMBER)

        assert len(group.members) == 1
        assert group.members[0].user_id == user_id
        assert group.members[0].role == Role.MEMBER

    def test_adds_owner(self):
        """Test that owner can be added."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        owner_id = UserId.generate()

        group.add_member(owner_id, Role.OWNER)

        assert group.members[0].role == Role.OWNER

    def test_adds_multiple_members(self):
        """Test that multiple members can be added."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        alice = UserId.generate()
        bob = UserId.generate()

        group.add_member(alice, Role.OWNER)
        group.add_member(bob, Role.MEMBER)

        assert len(group.members) == 2

    def test_prevents_duplicate_members(self):
        """Test that same user cannot be added twice."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        group.add_member(user_id, Role.MEMBER)

        with pytest.raises(ValueError, match="already a member"):
            group.add_member(user_id, Role.ADMIN)


class TestHasMember:
    """Tests for Group.has_member() method."""

    def test_returns_true_when_member_exists(self):
        """Test that has_member returns True for existing member."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, Role.MEMBER)

        assert group.has_member(user_id) is True

    def test_returns_false_when_member_does_not_exist(self):
        """Test that has_member returns False for non-member."""
        group = Group(
            id=GroupId.generate(),
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
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, Role.ADMIN)

        role = group.get_member_role(user_id)

        assert role == Role.ADMIN

    def test_returns_none_for_non_member(self):
        """Test that get_member_role returns None for non-member."""
        group = Group(
            id=GroupId.generate(),
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
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, Role.MEMBER)

        group.remove_member(user_id)

        assert len(group.members) == 0
        assert not group.has_member(user_id)

    def test_raises_when_removing_non_member(self):
        """Test that removing non-member raises error."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        with pytest.raises(ValueError, match="not a member"):
            group.remove_member(user_id)

    def test_prevents_removing_last_owner(self):
        """Test that last owner cannot be removed."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        owner_id = UserId.generate()
        group.add_member(owner_id, Role.OWNER)

        with pytest.raises(ValueError, match="last owner"):
            group.remove_member(owner_id)

    def test_can_remove_owner_when_multiple_owners_exist(self):
        """Test that owner can be removed if other owners exist."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        owner1 = UserId.generate()
        owner2 = UserId.generate()
        group.add_member(owner1, Role.OWNER)
        group.add_member(owner2, Role.OWNER)

        group.remove_member(owner1)

        assert len(group.members) == 1
        assert group.has_member(owner2)


class TestUpdateMemberRole:
    """Tests for Group.update_member_role() business logic."""

    def test_updates_member_role(self):
        """Test that member role can be updated."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, Role.MEMBER)

        group.update_member_role(user_id, Role.ADMIN)

        assert group.get_member_role(user_id) == Role.ADMIN

    def test_raises_when_updating_non_member(self):
        """Test that updating non-member raises error."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()

        with pytest.raises(ValueError, match="not a member"):
            group.update_member_role(user_id, Role.ADMIN)

    def test_prevents_demoting_last_owner(self):
        """Test that last owner cannot be demoted."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        owner_id = UserId.generate()
        group.add_member(owner_id, Role.OWNER)

        with pytest.raises(ValueError, match="last owner"):
            group.update_member_role(owner_id, Role.ADMIN)

    def test_can_demote_owner_when_multiple_owners_exist(self):
        """Test that owner can be demoted if other owners exist."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        owner1 = UserId.generate()
        owner2 = UserId.generate()
        group.add_member(owner1, Role.OWNER)
        group.add_member(owner2, Role.OWNER)

        group.update_member_role(owner1, Role.ADMIN)

        assert group.get_member_role(owner1) == Role.ADMIN
