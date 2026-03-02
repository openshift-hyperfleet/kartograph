"""Unit tests for Tenant aggregate (TDD).

Following TDD: Write tests that describe the desired behavior,
then implement the Tenant aggregate to make these tests pass.
"""

import pytest
from datetime import datetime, UTC

from iam.domain.aggregates import Tenant
from iam.domain.events import TenantCreated, TenantMemberAdded, TenantMemberRemoved
from iam.domain.exceptions import CannotRemoveLastAdminError
from iam.domain.value_objects import TenantId, TenantRole, UserId


class TestTenantCreation:
    """Tests for Tenant aggregate creation."""

    def test_creates_with_required_fields(self):
        """Test that Tenant can be created with required fields."""
        tenant_id = TenantId.generate()
        name = "Acme Corp"

        tenant = Tenant(id=tenant_id, name=name)

        assert tenant.id == tenant_id
        assert tenant.name == name

    def test_requires_id(self):
        """Test that Tenant requires an id."""
        with pytest.raises(TypeError):
            Tenant(name="Acme Corp")

    def test_requires_name(self):
        """Test that Tenant requires a name."""
        with pytest.raises(TypeError):
            Tenant(id=TenantId.generate())


class TestTenantFactory:
    """Tests for Tenant.create() factory method."""

    def test_factory_creates_tenant_with_generated_id(self):
        """Factory should generate an ID for the tenant."""
        tenant = Tenant.create(name="Acme Corp")

        assert tenant.id is not None
        assert tenant.name == "Acme Corp"

    def test_factory_records_tenant_created_event(self):
        """Factory should record a TenantCreated event."""
        tenant = Tenant.create(name="Acme Corp")
        events = tenant.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], TenantCreated)
        assert events[0].tenant_id == tenant.id.value
        assert events[0].name == "Acme Corp"
        assert isinstance(events[0].occurred_at, datetime)

    def test_factory_event_has_utc_timestamp(self):
        """Factory should use UTC timestamp in event."""
        tenant = Tenant.create(name="Acme Corp")
        events = tenant.collect_events()

        # Verify the timestamp is recent and in UTC
        assert events[0].occurred_at.tzinfo == UTC
        time_diff = datetime.now(UTC) - events[0].occurred_at
        assert time_diff.total_seconds() < 1  # Should be very recent


class TestAddMember:
    """Tests for Tenant.add_member() business logic."""

    def test_adds_member_with_admin_role(self):
        """Test that member can be added with admin role."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.add_member(user_id, TenantRole.ADMIN, added_by=admin_id)

        events = tenant.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TenantMemberAdded)

    def test_adds_member_with_member_role(self):
        """Test that member can be added with member role."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.add_member(user_id, TenantRole.MEMBER, added_by=admin_id)

        events = tenant.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TenantMemberAdded)

    def test_add_member_records_event_with_correct_data(self):
        """Test that add_member records event with all correct data."""
        tenant_id = TenantId.generate()
        tenant = Tenant(id=tenant_id, name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.add_member(user_id, TenantRole.ADMIN, added_by=admin_id)

        events = tenant.collect_events()
        event = events[0]

        assert event.tenant_id == tenant_id.value
        assert event.user_id == user_id.value
        assert event.role == TenantRole.ADMIN.value
        assert event.added_by == admin_id.value
        assert isinstance(event.occurred_at, datetime)

    def test_add_member_without_added_by_is_system_action(self):
        """Test that member can be added without added_by for system actions."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")

        # System action - no added_by
        tenant.add_member(user_id, TenantRole.ADMIN)

        events = tenant.collect_events()
        event = events[0]

        assert event.added_by is None

    def test_add_member_event_has_utc_timestamp(self):
        """Test that add_member event has UTC timestamp."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")

        tenant.add_member(user_id, TenantRole.MEMBER)

        events = tenant.collect_events()
        assert events[0].occurred_at.tzinfo == UTC

    def test_can_add_multiple_members(self):
        """Test that multiple members can be added."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user1 = UserId.from_string("user-1")
        user2 = UserId.from_string("user-2")
        user3 = UserId.from_string("user-3")

        tenant.add_member(user1, TenantRole.ADMIN)
        tenant.add_member(user2, TenantRole.MEMBER)
        tenant.add_member(user3, TenantRole.MEMBER)

        events = tenant.collect_events()
        assert len(events) == 3
        assert all(isinstance(e, TenantMemberAdded) for e in events)


class TestAddMemberRoleReplacement:
    """Tests for role replacement in Tenant.add_member()."""

    def test_replaces_role_when_current_role_differs(self):
        """Test that add_member emits MemberRemoved + MemberAdded when replacing role."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.add_member(
            user_id, TenantRole.MEMBER, added_by=admin_id, current_role=TenantRole.ADMIN
        )

        events = tenant.collect_events()
        assert len(events) == 2
        assert isinstance(events[0], TenantMemberRemoved)
        assert events[0].role == TenantRole.ADMIN.value
        assert events[0].user_id == user_id.value
        assert isinstance(events[1], TenantMemberAdded)
        assert events[1].role == TenantRole.MEMBER.value

    def test_no_removal_when_current_role_is_same(self):
        """Test that add_member does NOT emit MemberRemoved when role is the same."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")

        tenant.add_member(user_id, TenantRole.ADMIN, current_role=TenantRole.ADMIN)

        events = tenant.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TenantMemberAdded)

    def test_no_removal_when_no_current_role(self):
        """Test that add_member does NOT emit MemberRemoved for new members."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")

        tenant.add_member(user_id, TenantRole.MEMBER, current_role=None)

        events = tenant.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TenantMemberAdded)

    def test_replacement_event_carries_removed_by(self):
        """Test that the removal event during role replacement carries removed_by."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.add_member(
            user_id, TenantRole.MEMBER, added_by=admin_id, current_role=TenantRole.ADMIN
        )

        events = tenant.collect_events()
        removed_event = events[0]
        assert removed_event.removed_by == admin_id.value

    def test_cannot_replace_last_admin_role(self):
        """Role replacement should raise CannotRemoveLastAdminError when demoting last admin."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        with pytest.raises(CannotRemoveLastAdminError):
            tenant.add_member(
                user_id,
                TenantRole.MEMBER,
                added_by=admin_id,
                current_role=TenantRole.ADMIN,
                is_last_admin=True,
            )

    def test_no_events_on_last_admin_role_replacement_failure(self):
        """No events should be emitted when last-admin role replacement fails."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        try:
            tenant.add_member(
                user_id,
                TenantRole.MEMBER,
                added_by=admin_id,
                current_role=TenantRole.ADMIN,
                is_last_admin=True,
            )
        except CannotRemoveLastAdminError:
            pass

        events = tenant.collect_events()
        assert len(events) == 0

    def test_can_replace_admin_role_when_not_last_admin(self):
        """Role replacement should succeed when is_last_admin=False."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.add_member(
            user_id,
            TenantRole.MEMBER,
            added_by=admin_id,
            current_role=TenantRole.ADMIN,
            is_last_admin=False,
        )

        events = tenant.collect_events()
        assert len(events) == 2
        assert isinstance(events[0], TenantMemberRemoved)
        assert isinstance(events[1], TenantMemberAdded)


class TestGetMemberRole:
    """Tests for Tenant.get_member_role() helper."""

    def test_returns_role_from_pending_events(self):
        """Test that get_member_role reads from pending events."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")

        tenant.add_member(user_id, TenantRole.ADMIN)

        assert tenant.get_member_role(user_id) == TenantRole.ADMIN

    def test_returns_none_for_unknown_user(self):
        """Test that get_member_role returns None for unknown users."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")

        assert tenant.get_member_role(user_id) is None

    def test_returns_none_after_removal(self):
        """Test that get_member_role returns None after user is removed."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.add_member(user_id, TenantRole.ADMIN)
        tenant.remove_member(user_id, removed_by=admin_id, is_last_admin=False)

        assert tenant.get_member_role(user_id) is None


class TestRemoveMember:
    """Tests for Tenant.remove_member() business logic."""

    def test_removes_member_when_not_last_admin(self):
        """Test that member can be removed when not the last admin."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.remove_member(
            user_id=user_id,
            removed_by=admin_id,
            is_last_admin=False,
        )

        events = tenant.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TenantMemberRemoved)

    def test_remove_member_records_event_with_correct_data(self):
        """Test that remove_member records event with all correct data."""
        tenant_id = TenantId.generate()
        tenant = Tenant(id=tenant_id, name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.remove_member(
            user_id=user_id,
            removed_by=admin_id,
            is_last_admin=False,
        )

        events = tenant.collect_events()
        event = events[0]

        assert event.tenant_id == tenant_id.value
        assert event.user_id == user_id.value
        assert event.removed_by == admin_id.value
        assert isinstance(event.occurred_at, datetime)

    def test_remove_member_event_has_utc_timestamp(self):
        """Test that remove_member event has UTC timestamp."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        tenant.remove_member(
            user_id=user_id,
            removed_by=admin_id,
            is_last_admin=False,
        )

        events = tenant.collect_events()
        assert events[0].occurred_at.tzinfo == UTC

    def test_cannot_remove_last_admin(self):
        """Test that last admin cannot be removed."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        with pytest.raises(CannotRemoveLastAdminError):
            tenant.remove_member(
                user_id=user_id,
                removed_by=admin_id,
                is_last_admin=True,
            )

    def test_cannot_remove_last_admin_does_not_record_event(self):
        """Test that failed removal does not record event."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        try:
            tenant.remove_member(
                user_id=user_id,
                removed_by=admin_id,
                is_last_admin=True,
            )
        except CannotRemoveLastAdminError:
            pass

        events = tenant.collect_events()
        assert len(events) == 0

    def test_can_remove_regular_member(self):
        """Test that regular members can be removed."""
        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        member_id = UserId.from_string("member-123")
        admin_id = UserId.from_string("admin-456")

        # Members can always be removed (is_last_admin=False)
        tenant.remove_member(
            user_id=member_id,
            removed_by=admin_id,
            is_last_admin=False,
        )

        events = tenant.collect_events()
        assert len(events) == 1


class TestEventCollection:
    """Tests for event collection behavior."""

    def test_collect_events_clears_pending_events(self):
        """Test that collect_events clears the pending events list."""
        tenant = Tenant.create(name="Acme Corp")

        events1 = tenant.collect_events()
        events2 = tenant.collect_events()

        assert len(events1) == 1
        assert len(events2) == 0

    def test_events_accumulate_before_collection(self):
        """Test that events accumulate before being collected."""
        tenant = Tenant.create(name="Acme Corp")
        user1 = UserId.from_string("user-1")
        user2 = UserId.from_string("user-2")

        # Don't collect events yet
        tenant.add_member(user1, TenantRole.ADMIN)
        tenant.add_member(user2, TenantRole.MEMBER)

        # Now collect - should have 3 events (1 create + 2 add_member)
        events = tenant.collect_events()
        assert len(events) == 3

    def test_multiple_operations_create_multiple_events(self):
        """Test that multiple operations create separate events."""
        tenant = Tenant.create(name="Acme Corp")
        user1 = UserId.from_string("user-1")
        user2 = UserId.from_string("user-2")
        admin = UserId.from_string("admin")

        tenant.add_member(user1, TenantRole.ADMIN, added_by=admin)
        tenant.add_member(user2, TenantRole.MEMBER, added_by=admin)
        tenant.remove_member(user2, removed_by=admin, is_last_admin=False)

        events = tenant.collect_events()

        # 1 TenantCreated + 2 TenantMemberAdded + 1 TenantMemberRemoved
        assert len(events) == 4
        assert isinstance(events[0], TenantCreated)
        assert isinstance(events[1], TenantMemberAdded)
        assert isinstance(events[2], TenantMemberAdded)
        assert isinstance(events[3], TenantMemberRemoved)


class TestMarkForDeletion:
    """Tests for Tenant.mark_for_deletion()."""

    def test_mark_for_deletion_records_event(self):
        """Test that mark_for_deletion records TenantDeleted event."""
        from iam.domain.events import TenantDeleted

        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        members = []  # Empty tenant

        tenant.mark_for_deletion(members=members)

        events = tenant.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TenantDeleted)

    def test_mark_for_deletion_event_has_correct_data(self):
        """Test that TenantDeleted event has correct data."""

        tenant_id = TenantId.generate()
        tenant = Tenant(id=tenant_id, name="Acme Corp")
        members = []  # Empty tenant

        tenant.mark_for_deletion(members=members)

        events = tenant.collect_events()
        event = events[0]

        assert event.tenant_id == tenant_id.value
        assert isinstance(event.occurred_at, datetime)
        assert event.occurred_at.tzinfo == UTC
        assert event.members == ()

    def test_mark_for_deletion_captures_member_snapshot(self):
        """Test that mark_for_deletion captures snapshot of tenant members."""
        from iam.domain.events import MemberSnapshot, TenantDeleted

        tenant = Tenant(id=TenantId.generate(), name="Acme Corp")
        members = [
            ("user-123", "admin"),
            ("user-456", "member"),
            ("user-789", "admin"),
        ]

        tenant.mark_for_deletion(members=members)

        events = tenant.collect_events()
        event = events[0]

        assert isinstance(event, TenantDeleted)
        assert len(event.members) == 3
        assert all(isinstance(m, MemberSnapshot) for m in event.members)
        assert event.members[0].user_id == "user-123"
        assert event.members[0].role == "admin"
        assert event.members[1].user_id == "user-456"
        assert event.members[1].role == "member"
        assert event.members[2].user_id == "user-789"
        assert event.members[2].role == "admin"
        assert event.occurred_at.tzinfo == UTC
