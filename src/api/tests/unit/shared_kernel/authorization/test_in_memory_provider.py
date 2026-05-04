"""Unit tests for InMemoryAuthorizationProvider.

Covers all spec scenarios from specs/shared-kernel/spicedb-authorization.spec.md.
Uses the InMemoryAuthorizationProvider fake to exercise the AuthorizationProvider
protocol contract without requiring a running SpiceDB instance.

Each test class maps to a Requirement in the spec, with individual tests
covering each Scenario.
"""

import pytest

from shared_kernel.authorization.protocols import CheckRequest
from shared_kernel.authorization.types import RelationshipSpec
from tests.fakes.authorization import InMemoryAuthorizationProvider


# ---------------------------------------------------------------------------
# Requirement: Permission Checking
# ---------------------------------------------------------------------------


class TestPermissionChecking:
    """Tests for Requirement: Permission Checking.

    The system SHALL evaluate whether a subject has a specific permission
    on a resource.
    """

    @pytest.mark.asyncio
    async def test_permission_granted_via_direct_relationship(self):
        """Scenario: Permission granted.

        GIVEN a user with a relationship that grants `view` permission on a workspace
        WHEN a permission check is performed
        THEN the check returns true
        """
        provider = InMemoryAuthorizationProvider()
        await provider.write_relationship(
            resource="workspace:ws-abc",
            relation="member",
            subject="user:alice",
        )

        result = await provider.check_permission(
            resource="workspace:ws-abc",
            permission="view",
            subject="user:alice",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_permission_denied_without_relationship(self):
        """Scenario: Permission denied.

        GIVEN a user with no relationships granting `manage` permission on a workspace
        WHEN a permission check is performed
        THEN the check returns false
        """
        provider = InMemoryAuthorizationProvider()
        # Write a view-only relationship (member → view, NOT manage)
        await provider.write_relationship(
            resource="workspace:ws-abc",
            relation="member",
            subject="user:alice",
        )

        result = await provider.check_permission(
            resource="workspace:ws-abc",
            permission="manage",
            subject="user:alice",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_permission_denied_for_unrelated_user(self):
        """Scenario: Permission denied for a user with no relationships at all."""
        provider = InMemoryAuthorizationProvider()

        result = await provider.check_permission(
            resource="workspace:ws-abc",
            permission="view",
            subject="user:bob",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_computed_permission_via_group_inheritance(self):
        """Scenario: Computed permission via inheritance.

        GIVEN a user who is a member of a group assigned to a workspace
        WHEN a permission check for `edit` is performed on the workspace
        THEN the permission is computed through the group relationship chain
        """
        provider = InMemoryAuthorizationProvider()

        # alice is a member of the engineering group
        await provider.write_relationship(
            resource="group:eng",
            relation="member_relation",
            subject="user:alice",
        )

        # The engineering group (via #member relation) is an editor of workspace ws-1
        await provider.write_relationship(
            resource="workspace:ws-1",
            relation="editor",
            subject="group:eng#member",
        )

        # alice should be able to edit via group membership
        result = await provider.check_permission(
            resource="workspace:ws-1",
            permission="edit",
            subject="user:alice",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_admin_grants_view_permission(self):
        """Verify admin relation grants view permission (permission composition)."""
        provider = InMemoryAuthorizationProvider()
        await provider.write_relationship(
            resource="workspace:ws-1",
            relation="admin",
            subject="user:alice",
        )

        result = await provider.check_permission(
            resource="workspace:ws-1",
            permission="view",
            subject="user:alice",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_admin_grants_manage_permission(self):
        """Verify admin relation grants manage permission."""
        provider = InMemoryAuthorizationProvider()
        await provider.write_relationship(
            resource="workspace:ws-1",
            relation="admin",
            subject="user:alice",
        )

        result = await provider.check_permission(
            resource="workspace:ws-1",
            permission="manage",
            subject="user:alice",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_editor_does_not_grant_manage_permission(self):
        """Verify editor relation does NOT grant manage permission."""
        provider = InMemoryAuthorizationProvider()
        await provider.write_relationship(
            resource="workspace:ws-1",
            relation="editor",
            subject="user:alice",
        )

        result = await provider.check_permission(
            resource="workspace:ws-1",
            permission="manage",
            subject="user:alice",
        )

        assert result is False


# ---------------------------------------------------------------------------
# Requirement: Bulk Permission Checking
# ---------------------------------------------------------------------------


class TestBulkPermissionChecking:
    """Tests for Requirement: Bulk Permission Checking.

    The system SHALL support checking permissions across multiple resources
    in a single operation.
    """

    @pytest.mark.asyncio
    async def test_bulk_check_filters_accessible_resources(self):
        """Scenario: Filter accessible resources.

        GIVEN a list of resource IDs and a permission to check
        WHEN a bulk check is performed
        THEN only the resource IDs the user has permission on are returned
        """
        provider = InMemoryAuthorizationProvider()

        # alice has view on ws-A and ws-B but not ws-C
        await provider.write_relationship(
            resource="workspace:ws-A",
            relation="admin",
            subject="user:alice",
        )
        await provider.write_relationship(
            resource="workspace:ws-B",
            relation="member",
            subject="user:alice",
        )
        # ws-C has no relationship for alice

        requests = [
            CheckRequest(
                resource="workspace:ws-A", permission="view", subject="user:alice"
            ),
            CheckRequest(
                resource="workspace:ws-B", permission="view", subject="user:alice"
            ),
            CheckRequest(
                resource="workspace:ws-C", permission="view", subject="user:alice"
            ),
        ]

        result = await provider.bulk_check_permission(requests)

        assert "workspace:ws-A" in result
        assert "workspace:ws-B" in result
        assert "workspace:ws-C" not in result
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_bulk_check_returns_empty_set_when_no_permissions(self):
        """Bulk check returns empty set when user has no permissions on any resource."""
        provider = InMemoryAuthorizationProvider()

        requests = [
            CheckRequest(
                resource="workspace:ws-A", permission="view", subject="user:alice"
            ),
            CheckRequest(
                resource="workspace:ws-B", permission="view", subject="user:alice"
            ),
        ]

        result = await provider.bulk_check_permission(requests)

        assert result == set()

    @pytest.mark.asyncio
    async def test_bulk_check_returns_all_when_all_permitted(self):
        """Bulk check returns all resources when user has all permissions."""
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")
        await provider.write_relationship("workspace:ws-2", "admin", "user:alice")

        requests = [
            CheckRequest(
                resource="workspace:ws-1", permission="manage", subject="user:alice"
            ),
            CheckRequest(
                resource="workspace:ws-2", permission="manage", subject="user:alice"
            ),
        ]

        result = await provider.bulk_check_permission(requests)

        assert result == {"workspace:ws-1", "workspace:ws-2"}


# ---------------------------------------------------------------------------
# Requirement: Relationship Writes
# ---------------------------------------------------------------------------


class TestRelationshipWrites:
    """Tests for Requirement: Relationship Writes.

    The system SHALL create explicit relationships between subjects and resources.
    """

    @pytest.mark.asyncio
    async def test_single_relationship_write_reflects_in_future_checks(self):
        """Scenario: Single relationship.

        GIVEN a user and a workspace
        WHEN a relationship write creates `workspace#admin@user:alice`
        THEN future permission checks reflect the new relationship
        """
        provider = InMemoryAuthorizationProvider()

        # Before write: no permission
        assert not await provider.check_permission(
            resource="workspace:ws-1",
            permission="manage",
            subject="user:alice",
        )

        # Write the relationship
        await provider.write_relationship(
            resource="workspace:ws-1",
            relation="admin",
            subject="user:alice",
        )

        # After write: permission granted
        assert await provider.check_permission(
            resource="workspace:ws-1",
            permission="manage",
            subject="user:alice",
        )

    @pytest.mark.asyncio
    async def test_bulk_relationships_write_creates_all(self):
        """Scenario: Bulk relationships.

        GIVEN multiple relationships to write
        WHEN a bulk write is performed
        THEN all relationships are created atomically
        """
        provider = InMemoryAuthorizationProvider()

        relationships = [
            RelationshipSpec(
                resource="workspace:ws-1", relation="admin", subject="user:alice"
            ),
            RelationshipSpec(
                resource="workspace:ws-1", relation="editor", subject="user:bob"
            ),
            RelationshipSpec(
                resource="workspace:ws-2", relation="member", subject="user:charlie"
            ),
        ]

        await provider.write_relationships(relationships)

        # All should be reflected in permission checks
        assert await provider.check_permission("workspace:ws-1", "manage", "user:alice")
        assert await provider.check_permission("workspace:ws-1", "edit", "user:bob")
        assert await provider.check_permission("workspace:ws-2", "view", "user:charlie")

    @pytest.mark.asyncio
    async def test_write_relationship_is_idempotent(self):
        """Writing the same relationship twice does not create duplicate entries."""
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")
        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")

        # Should still only have one entry
        tuples = await provider.read_relationships(
            resource_type="workspace",
            resource_id="ws-1",
            relation="admin",
        )
        assert len(tuples) == 1


# ---------------------------------------------------------------------------
# Requirement: Relationship Deletion
# ---------------------------------------------------------------------------


class TestRelationshipDeletion:
    """Tests for Requirement: Relationship Deletion.

    The system SHALL delete explicit relationships between subjects and resources.
    """

    @pytest.mark.asyncio
    async def test_single_deletion_removes_relationship(self):
        """Scenario: Single deletion.

        GIVEN an existing relationship `workspace#admin@user:alice`
        WHEN the relationship is deleted
        THEN future permission checks no longer include it
        """
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")

        # Confirm permission exists
        assert await provider.check_permission("workspace:ws-1", "manage", "user:alice")

        # Delete the relationship
        await provider.delete_relationship("workspace:ws-1", "admin", "user:alice")

        # Permission no longer granted
        assert not await provider.check_permission(
            "workspace:ws-1", "manage", "user:alice"
        )

    @pytest.mark.asyncio
    async def test_filter_based_deletion_removes_matching_relationships(self):
        """Scenario: Filter-based deletion.

        GIVEN a resource with multiple relationships
        WHEN relationships are deleted by filter (e.g., all relationships for a specific resource)
        THEN all matching relationships are removed
        AND at least one filter criterion beyond resource type is required
        """
        provider = InMemoryAuthorizationProvider()

        # Set up multiple relationships for workspace ws-1
        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")
        await provider.write_relationship("workspace:ws-1", "editor", "user:bob")
        await provider.write_relationship("workspace:ws-2", "admin", "user:charlie")

        # Delete all relationships for workspace ws-1 (filtered by resource_id)
        await provider.delete_relationships_by_filter(
            resource_type="workspace",
            resource_id="ws-1",
        )

        # ws-1 relationships gone
        assert not await provider.check_permission(
            "workspace:ws-1", "view", "user:alice"
        )
        assert not await provider.check_permission("workspace:ws-1", "view", "user:bob")

        # ws-2 relationship unaffected
        assert await provider.check_permission("workspace:ws-2", "view", "user:charlie")

    @pytest.mark.asyncio
    async def test_filter_based_deletion_requires_extra_filter(self):
        """At least one filter criterion beyond resource type is required.

        Per spec: AND at least one filter criterion beyond resource type is required.
        """
        provider = InMemoryAuthorizationProvider()

        with pytest.raises(ValueError, match="At least one filter parameter"):
            await provider.delete_relationships_by_filter(
                resource_type="workspace",
            )

    @pytest.mark.asyncio
    async def test_filter_based_deletion_by_relation(self):
        """Filter-based deletion can target a specific relation."""
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")
        await provider.write_relationship("workspace:ws-1", "member", "user:alice")

        # Delete only the admin relation for ws-1
        await provider.delete_relationships_by_filter(
            resource_type="workspace",
            resource_id="ws-1",
            relation="admin",
        )

        # admin gone
        assert not await provider.check_permission(
            "workspace:ws-1", "manage", "user:alice"
        )
        # member still present (view still granted)
        assert await provider.check_permission("workspace:ws-1", "view", "user:alice")

    @pytest.mark.asyncio
    async def test_bulk_deletion_removes_specified_relationships(self):
        """Bulk delete removes only specified relationships."""
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")
        await provider.write_relationship("workspace:ws-1", "editor", "user:bob")

        await provider.delete_relationships(
            [
                RelationshipSpec(
                    resource="workspace:ws-1", relation="admin", subject="user:alice"
                )
            ]
        )

        assert not await provider.check_permission(
            "workspace:ws-1", "manage", "user:alice"
        )
        assert await provider.check_permission("workspace:ws-1", "edit", "user:bob")


# ---------------------------------------------------------------------------
# Requirement: Resource Lookup
# ---------------------------------------------------------------------------


class TestResourceLookup:
    """Tests for Requirement: Resource Lookup.

    The system SHALL find all resources a subject has a specific permission on.
    """

    @pytest.mark.asyncio
    async def test_lookup_accessible_workspaces(self):
        """Scenario: Lookup accessible workspaces.

        GIVEN a user with `view` permission on workspaces A and B
        WHEN a resource lookup is performed for `view` permission
        THEN workspace IDs A and B are returned
        """
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("workspace:ws-A", "member", "user:alice")
        await provider.write_relationship("workspace:ws-B", "admin", "user:alice")
        # ws-C has no relationship for alice

        result = await provider.lookup_resources(
            resource_type="workspace",
            permission="view",
            subject="user:alice",
        )

        assert set(result) == {"ws-A", "ws-B"}

    @pytest.mark.asyncio
    async def test_lookup_returns_empty_when_no_accessible_resources(self):
        """Lookup returns empty list when user has no permissions."""
        provider = InMemoryAuthorizationProvider()

        result = await provider.lookup_resources(
            resource_type="workspace",
            permission="view",
            subject="user:alice",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_lookup_resources_respects_permission_level(self):
        """Lookup with `manage` permission returns only admin-role resources."""
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("workspace:ws-A", "admin", "user:alice")
        await provider.write_relationship("workspace:ws-B", "member", "user:alice")

        # Only ws-A grants manage (admin relation required)
        result = await provider.lookup_resources(
            resource_type="workspace",
            permission="manage",
            subject="user:alice",
        )

        assert set(result) == {"ws-A"}


# ---------------------------------------------------------------------------
# Requirement: Relationship Reading
# ---------------------------------------------------------------------------


class TestRelationshipReading:
    """Tests for Requirement: Relationship Reading.

    The system SHALL read explicit (non-computed) relationship tuples.
    """

    @pytest.mark.asyncio
    async def test_read_explicit_tuples_only(self):
        """Scenario: Read explicit tuples.

        GIVEN a workspace with explicit admin and editor relationships
        WHEN relationships are read for the workspace
        THEN only the directly-written tuples are returned
        AND computed permissions are NOT included
        """
        provider = InMemoryAuthorizationProvider()

        # Write explicit admin and editor relationships
        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")
        await provider.write_relationship("workspace:ws-1", "editor", "user:bob")

        tuples = await provider.read_relationships(
            resource_type="workspace",
            resource_id="ws-1",
        )

        # Should return exactly the two written tuples
        assert len(tuples) == 2
        resources = {t.resource for t in tuples}
        relations = {t.relation for t in tuples}
        subjects = {t.subject for t in tuples}

        assert resources == {"workspace:ws-1"}
        assert "admin" in relations
        assert "editor" in relations
        assert "user:alice" in subjects
        assert "user:bob" in subjects

    @pytest.mark.asyncio
    async def test_read_relationships_filters_by_relation(self):
        """Read relationships can filter by relation name."""
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("workspace:ws-1", "admin", "user:alice")
        await provider.write_relationship("workspace:ws-1", "editor", "user:bob")

        tuples = await provider.read_relationships(
            resource_type="workspace",
            resource_id="ws-1",
            relation="admin",
        )

        assert len(tuples) == 1
        assert tuples[0].relation == "admin"
        assert tuples[0].subject == "user:alice"

    @pytest.mark.asyncio
    async def test_read_relationships_returns_empty_when_none_match(self):
        """Read relationships returns empty list when no tuples match."""
        provider = InMemoryAuthorizationProvider()

        tuples = await provider.read_relationships(
            resource_type="workspace",
            resource_id="ws-nonexistent",
        )

        assert tuples == []

    @pytest.mark.asyncio
    async def test_read_relationships_does_not_return_computed_permissions(self):
        """Computed permissions (via group chain) are NOT returned by read_relationships.

        read_relationships returns only the explicitly-written tuples.
        The alice→view permission derived from group membership is NOT a stored tuple.
        """
        provider = InMemoryAuthorizationProvider()

        # Write group membership and group-workspace assignment
        await provider.write_relationship("group:eng", "member_relation", "user:alice")
        await provider.write_relationship(
            "workspace:ws-1", "editor", "group:eng#member"
        )

        tuples = await provider.read_relationships(
            resource_type="workspace",
            resource_id="ws-1",
        )

        # Only the group assignment should be present (explicit tuple)
        # The user:alice direct permission should NOT appear
        subjects = {t.subject for t in tuples}
        assert "user:alice" not in subjects
        assert "group:eng#member" in subjects


# ---------------------------------------------------------------------------
# Requirement: Subject Relations for Groups
# ---------------------------------------------------------------------------


class TestSubjectRelationsForGroups:
    """Tests for Requirement: Subject Relations for Groups.

    The system SHALL use subject relations when writing group-based workspace grants.
    """

    @pytest.mark.asyncio
    async def test_group_workspace_assignment_uses_member_relation(self):
        """Scenario: Group workspace assignment.

        GIVEN a group being assigned the `editor` role on a workspace
        WHEN the relationship is written
        THEN it uses the form `workspace#editor@group:grp123#member`
        AND the `#member` subject relation ensures all group members inherit the permission
        """
        provider = InMemoryAuthorizationProvider()

        # Assign group grp123 as editor of workspace ws-1 using #member subject relation
        await provider.write_relationship(
            resource="workspace:ws-1",
            relation="editor",
            subject="group:grp123#member",
        )

        # Verify the tuple is stored with the correct subject form
        tuples = await provider.read_relationships(
            resource_type="workspace",
            resource_id="ws-1",
        )

        assert len(tuples) == 1
        assert tuples[0].subject == "group:grp123#member"

    @pytest.mark.asyncio
    async def test_group_members_inherit_workspace_permission_via_member_relation(self):
        """All group members inherit workspace permissions when assigned via #member.

        GIVEN grp123#member is assigned editor on workspace ws-1
        AND user alice is a member of grp123
        WHEN alice checks edit permission on ws-1
        THEN permission is granted (via group membership chain)
        """
        provider = InMemoryAuthorizationProvider()

        # alice is member of group grp123
        await provider.write_relationship(
            "group:grp123", "member_relation", "user:alice"
        )

        # grp123#member is editor of workspace ws-1
        await provider.write_relationship(
            "workspace:ws-1", "editor", "group:grp123#member"
        )

        # alice should inherit edit permission through the chain
        result = await provider.check_permission(
            resource="workspace:ws-1",
            permission="edit",
            subject="user:alice",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_non_group_members_do_not_inherit_permission(self):
        """Users not in the group do NOT inherit permissions."""
        provider = InMemoryAuthorizationProvider()

        # alice is member of grp123, but bob is not
        await provider.write_relationship(
            "group:grp123", "member_relation", "user:alice"
        )
        await provider.write_relationship(
            "workspace:ws-1", "editor", "group:grp123#member"
        )

        # bob should NOT have edit permission
        result = await provider.check_permission(
            resource="workspace:ws-1",
            permission="edit",
            subject="user:bob",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_group_admin_also_inherits_workspace_permission(self):
        """Group admins (not just member_relation) also inherit via #member.

        In the SpiceDB schema, group.member = admin + member_relation.
        So group admins are also group members and should inherit workspace permissions.
        """
        provider = InMemoryAuthorizationProvider()

        # alice is admin of group grp123 (not just member_relation)
        await provider.write_relationship("group:grp123", "admin", "user:alice")

        # grp123#member (which includes admins) is editor of workspace ws-1
        await provider.write_relationship(
            "workspace:ws-1", "editor", "group:grp123#member"
        )

        # alice (as group admin = group member) should have edit permission
        result = await provider.check_permission(
            resource="workspace:ws-1",
            permission="edit",
            subject="user:alice",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_lookup_subjects_for_group_membership(self):
        """lookup_subjects returns users who have a relation on a resource."""
        provider = InMemoryAuthorizationProvider()

        await provider.write_relationship("group:eng", "member_relation", "user:alice")
        await provider.write_relationship("group:eng", "member_relation", "user:bob")

        subjects = await provider.lookup_subjects(
            resource="group:eng",
            relation="member_relation",
            subject_type="user",
        )

        subject_ids = {s.subject_id for s in subjects}
        assert "alice" in subject_ids
        assert "bob" in subject_ids
