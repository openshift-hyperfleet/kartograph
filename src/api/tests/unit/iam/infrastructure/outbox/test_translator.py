"""Unit tests for IAMEventTranslator (TDD - tests first).

These tests verify that IAM domain events are correctly translated into
SpiceDB relationship operations using type-safe enums.
"""

import pytest

from iam.domain.value_objects import GroupRole, WorkspaceRole
from iam.infrastructure.outbox import IAMEventTranslator
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    DeleteRelationshipsByFilter,
    WriteRelationship,
)


class TestIAMEventTranslatorSupportedEvents:
    """Tests for supported event types."""

    def test_supports_all_iam_domain_events(self):
        """Translator should support all IAM domain event types."""
        translator = IAMEventTranslator()
        supported = translator.supported_event_types()

        assert "GroupCreated" in supported
        assert "GroupDeleted" in supported
        assert "MemberAdded" in supported
        assert "MemberRemoved" in supported
        assert "MemberRoleChanged" in supported
        assert "APIKeyCreated" in supported
        assert "APIKeyRevoked" in supported
        assert "WorkspaceMemberAdded" in supported
        assert "WorkspaceMemberRemoved" in supported
        assert "WorkspaceMemberRoleChanged" in supported


class TestIAMEventTranslatorGroupCreated:
    """Tests for GroupCreated translation."""

    def test_translates_group_created_to_tenant_relationship(self):
        """GroupCreated should produce a tenant relationship write."""
        translator = IAMEventTranslator()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("GroupCreated", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, WriteRelationship)
        assert op.resource_type == ResourceType.GROUP
        assert op.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert op.relation == RelationType.TENANT
        assert op.subject_type == ResourceType.TENANT
        assert op.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_formatted_resource_string(self):
        """Operation should format resource as type:id string."""
        translator = IAMEventTranslator()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("GroupCreated", payload)

        assert operations[0].resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[0].subject == "tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY"
        assert operations[0].relation_name == "tenant"


class TestIAMEventTranslatorGroupDeleted:
    """Tests for GroupDeleted translation."""

    def test_translates_group_deleted_without_members(self):
        """GroupDeleted with no members should only delete tenant relationship."""
        translator = IAMEventTranslator()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "members": [],
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("GroupDeleted", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, DeleteRelationship)
        assert op.resource_type == ResourceType.GROUP
        assert op.relation == RelationType.TENANT

    def test_translates_group_deleted_with_members(self):
        """GroupDeleted should delete tenant and all member relationships."""
        translator = IAMEventTranslator()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "members": [
                {"user_id": "user1", "role": "admin"},
                {"user_id": "user2", "role": "member"},
            ],
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("GroupDeleted", payload)

        # 1 tenant + 2 member deletes
        assert len(operations) == 3
        assert all(isinstance(op, DeleteRelationship) for op in operations)

        # First should be tenant relationship
        assert operations[0].relation == RelationType.TENANT

        # Members should be deleted with their roles
        member_ops = operations[1:]
        roles = [str(op.relation) for op in member_ops]
        assert "admin" in roles
        assert "member" in roles


class TestIAMEventTranslatorMemberAdded:
    """Tests for MemberAdded translation."""

    def test_translates_member_added_with_member_role(self):
        """MemberAdded with MEMBER role should produce member relationship."""
        translator = IAMEventTranslator()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "role": "member",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("MemberAdded", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, WriteRelationship)
        assert op.resource_type == ResourceType.GROUP
        assert op.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert op.relation == GroupRole.MEMBER
        assert op.subject_type == ResourceType.USER
        assert op.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNWW"

    def test_translates_member_added_with_admin_role(self):
        """MemberAdded with ADMIN role should produce admin relationship."""
        translator = IAMEventTranslator()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("MemberAdded", payload)

        assert operations[0].relation == GroupRole.ADMIN
        assert operations[0].relation_name == "admin"


class TestIAMEventTranslatorMemberRemoved:
    """Tests for MemberRemoved translation."""

    def test_translates_member_removed(self):
        """MemberRemoved should produce delete relationship operation."""
        translator = IAMEventTranslator()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "role": "member",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("MemberRemoved", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, DeleteRelationship)
        assert op.resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert op.relation_name == "member"
        assert op.subject == "user:01ARZCX0P0HZGQP3MZXQQ0NNWW"


class TestIAMEventTranslatorMemberRoleChanged:
    """Tests for MemberRoleChanged translation."""

    def test_translates_member_role_changed(self):
        """MemberRoleChanged should produce delete old + write new operations."""
        translator = IAMEventTranslator()
        payload = {
            "group_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "01ARZCX0P0HZGQP3MZXQQ0NNWW",
            "old_role": "member",
            "new_role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("MemberRoleChanged", payload)

        assert len(operations) == 2

        # First should delete old role
        delete_op = operations[0]
        assert isinstance(delete_op, DeleteRelationship)
        assert delete_op.relation_name == "member"

        # Second should write new role
        write_op = operations[1]
        assert isinstance(write_op, WriteRelationship)
        assert write_op.relation_name == "admin"


class TestIAMEventTranslatorAPIKeyCreated:
    """Tests for APIKeyCreated translation."""

    def test_translates_api_key_created_to_owner_and_tenant_relationships(self):
        """APIKeyCreated should produce owner and tenant relationship writes."""
        translator = IAMEventTranslator()
        payload = {
            "api_key_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "user-123-abc",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "name": "test-key",
            "prefix": "karto_abc123",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("APIKeyCreated", payload)

        assert len(operations) == 2

        # First: owner relationship
        owner_op = operations[0]
        assert isinstance(owner_op, WriteRelationship)
        assert owner_op.resource_type == ResourceType.API_KEY
        assert owner_op.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert owner_op.relation == RelationType.OWNER
        assert owner_op.subject_type == ResourceType.USER
        assert owner_op.subject_id == "user-123-abc"

        # Second: tenant relationship
        tenant_op = operations[1]
        assert isinstance(tenant_op, WriteRelationship)
        assert tenant_op.resource_type == ResourceType.API_KEY
        assert tenant_op.relation == RelationType.TENANT
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"


class TestIAMEventTranslatorAPIKeyRevoked:
    """Tests for APIKeyRevoked translation."""

    def test_translates_api_key_revoked_keeps_relationships_for_audit(self):
        """APIKeyRevoked should not delete relationships (audit trail).

        Revoked keys remain visible to owners and tenant admins for audit
        purposes. The is_revoked flag in PostgreSQL controls authentication.
        """
        translator = IAMEventTranslator()
        payload = {
            "api_key_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "user-123-abc",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("APIKeyRevoked", payload)

        # No SpiceDB operations - relationships stay intact
        assert len(operations) == 0


class TestIAMEventTranslatorAPIKeyDeleted:
    """Tests for APIKeyDeleted translation."""

    def test_translates_api_key_deleted_removes_all_relationships(self):
        """APIKeyDeleted should delete owner and tenant relationships.

        Used for cascade deletion when a tenant is deleted. Removes all
        SpiceDB relationships to prevent orphaned data.
        """
        translator = IAMEventTranslator()
        payload = {
            "api_key_id": "01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            "user_id": "user-123-abc",
            "tenant_id": "01ARZCX0P0HZGQP3MZXQQ0NNYY",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("APIKeyDeleted", payload)

        assert len(operations) == 2

        # First: delete owner relationship
        owner_delete = operations[0]
        assert isinstance(owner_delete, DeleteRelationship)
        assert owner_delete.resource_type == ResourceType.API_KEY
        assert owner_delete.resource_id == "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert owner_delete.relation == RelationType.OWNER
        assert owner_delete.subject_type == ResourceType.USER
        assert owner_delete.subject_id == "user-123-abc"

        # Second: delete tenant relationship
        tenant_delete = operations[1]
        assert isinstance(tenant_delete, DeleteRelationship)
        assert tenant_delete.resource_type == ResourceType.API_KEY
        assert tenant_delete.relation == RelationType.TENANT
        assert tenant_delete.subject_type == ResourceType.TENANT
        assert tenant_delete.subject_id == "01ARZCX0P0HZGQP3MZXQQ0NNYY"


class TestIAMEventTranslatorTenantMemberAdded:
    """Tests for TenantMemberAdded translation."""

    def test_translates_tenant_member_added_with_admin_role(self):
        """TenantMemberAdded with admin role should write admin relation."""
        translator = IAMEventTranslator()
        payload = {
            "tenant_id": "01TENANT123",
            "user_id": "user-456",
            "role": "admin",
            "added_by": "user-admin",
            "occurred_at": "2026-01-29T12:00:00+00:00",
        }

        operations = translator.translate("TenantMemberAdded", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, WriteRelationship)
        assert op.resource_type == ResourceType.TENANT
        assert op.resource_id == "01TENANT123"
        assert op.relation.value == "admin"
        assert op.subject_type == ResourceType.USER
        assert op.subject_id == "user-456"

    def test_translates_tenant_member_added_with_member_role(self):
        """TenantMemberAdded with member role should write member relation."""
        translator = IAMEventTranslator()
        payload = {
            "tenant_id": "01TENANT123",
            "user_id": "user-789",
            "role": "member",
            "added_by": None,
            "occurred_at": "2026-01-29T12:00:00+00:00",
        }

        operations = translator.translate("TenantMemberAdded", payload)

        assert len(operations) == 1
        op = operations[0]
        assert op.relation.value == "member"


class TestIAMEventTranslatorTenantMemberRemoved:
    """Tests for TenantMemberRemoved translation."""

    def test_translates_tenant_member_removed_deletes_all_roles(self):
        """TenantMemberRemoved should delete both member and admin relations.

        Deletes all possible tenant role relations to ensure cleanup
        regardless of what role the user actually had.
        """
        translator = IAMEventTranslator()
        payload = {
            "tenant_id": "01TENANT123",
            "user_id": "user-456",
            "removed_by": "user-admin",
            "occurred_at": "2026-01-29T12:00:00+00:00",
        }

        operations = translator.translate("TenantMemberRemoved", payload)

        # Should delete both admin and member relations
        assert len(operations) == 2

        # Verify both are delete operations for the tenant
        for op in operations:
            assert isinstance(op, DeleteRelationship)
            assert op.resource_type == ResourceType.TENANT
            assert op.resource_id == "01TENANT123"
            assert op.subject_type == ResourceType.USER
            assert op.subject_id == "user-456"

        # Verify both role relations are deleted
        relations = {op.relation.value for op in operations}
        assert relations == {"admin", "member"}


class TestIAMEventTranslatorTenantDeleted:
    """Tests for TenantDeleted translation."""

    def test_translates_tenant_deleted_with_no_members(self):
        """TenantDeleted with empty members should still delete root_workspace filter."""
        translator = IAMEventTranslator()
        payload = {
            "tenant_id": "01TENANT123",
            "members": [],
            "occurred_at": "2026-01-29T12:00:00+00:00",
        }

        operations = translator.translate("TenantDeleted", payload)

        # Should have exactly 1 operation: the filter-based root_workspace deletion
        assert len(operations) == 1
        filter_ops = [
            op for op in operations if isinstance(op, DeleteRelationshipsByFilter)
        ]
        assert len(filter_ops) == 1
        assert filter_ops[0].resource_type == ResourceType.TENANT
        assert filter_ops[0].resource_id == "01TENANT123"
        assert filter_ops[0].relation == RelationType.ROOT_WORKSPACE
        assert filter_ops[0].subject_type is None
        assert filter_ops[0].subject_id is None

    def test_translates_tenant_deleted_with_members(self):
        """TenantDeleted should delete root_workspace filter and all member relationships."""
        translator = IAMEventTranslator()
        payload = {
            "tenant_id": "01TENANT123",
            "members": [
                {"user_id": "user-admin-1", "role": "admin"},
                {"user_id": "user-admin-2", "role": "admin"},
                {"user_id": "user-member-1", "role": "member"},
            ],
            "occurred_at": "2026-01-29T12:00:00+00:00",
        }

        operations = translator.translate("TenantDeleted", payload)

        # 1 filter-based deletion + 3 member deletions
        assert len(operations) == 4

        # Check that DeleteRelationshipsByFilter for root_workspace is present
        filter_ops = [
            op for op in operations if isinstance(op, DeleteRelationshipsByFilter)
        ]
        assert len(filter_ops) == 1
        assert filter_ops[0].resource_type == ResourceType.TENANT
        assert filter_ops[0].resource_id == "01TENANT123"
        assert filter_ops[0].relation == RelationType.ROOT_WORKSPACE

        # Verify member delete operations
        member_ops = [op for op in operations if isinstance(op, DeleteRelationship)]
        assert len(member_ops) == 3
        for op in member_ops:
            assert op.resource_type == ResourceType.TENANT
            assert op.resource_id == "01TENANT123"
            assert op.subject_type == ResourceType.USER

        # Verify specific members
        deleted_members = {(op.subject_id, op.relation.value) for op in member_ops}
        assert deleted_members == {
            ("user-admin-1", "admin"),
            ("user-admin-2", "admin"),
            ("user-member-1", "member"),
        }

    def test_filter_based_deletion_is_first_operation(self):
        """Filter-based root_workspace deletion should precede member deletions."""
        translator = IAMEventTranslator()
        payload = {
            "tenant_id": "01TENANT123",
            "members": [
                {"user_id": "user-1", "role": "member"},
            ],
            "occurred_at": "2026-01-29T12:00:00+00:00",
        }

        operations = translator.translate("TenantDeleted", payload)

        # First operation should be the filter-based deletion
        assert isinstance(operations[0], DeleteRelationshipsByFilter)
        # Second should be the member deletion
        assert isinstance(operations[1], DeleteRelationship)


class TestIAMEventTranslatorWorkspaceCreated:
    """Tests for WorkspaceCreated translation."""

    def test_translate_workspace_created_root_workspace(self):
        """Root workspace creation should produce tenant and root_workspace relationships."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_ROOT",
            "tenant_id": "01TENANT_ABC",
            "name": "Root Workspace",
            "parent_workspace_id": None,
            "is_root": True,
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceCreated", payload)

        assert len(operations) == 2

        # First: workspace#tenant@tenant
        tenant_op = operations[0]
        assert isinstance(tenant_op, WriteRelationship)
        assert tenant_op.resource_type == ResourceType.WORKSPACE
        assert tenant_op.resource_id == "01WORKSPACE_ROOT"
        assert tenant_op.relation == RelationType.TENANT
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == "01TENANT_ABC"

        # Second: tenant#root_workspace@workspace
        root_op = operations[1]
        assert isinstance(root_op, WriteRelationship)
        assert root_op.resource_type == ResourceType.TENANT
        assert root_op.resource_id == "01TENANT_ABC"
        assert root_op.relation == RelationType.ROOT_WORKSPACE
        assert root_op.subject_type == ResourceType.WORKSPACE
        assert root_op.subject_id == "01WORKSPACE_ROOT"

    def test_translate_workspace_created_child_workspace(self):
        """Child workspace creation should produce tenant and parent relationships."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_CHILD",
            "tenant_id": "01TENANT_ABC",
            "name": "Engineering",
            "parent_workspace_id": "01WORKSPACE_ROOT",
            "is_root": False,
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceCreated", payload)

        assert len(operations) == 2

        # First: workspace#tenant@tenant
        tenant_op = operations[0]
        assert isinstance(tenant_op, WriteRelationship)
        assert tenant_op.resource_type == ResourceType.WORKSPACE
        assert tenant_op.resource_id == "01WORKSPACE_CHILD"
        assert tenant_op.relation == RelationType.TENANT
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == "01TENANT_ABC"

        # Second: workspace#parent@workspace
        parent_op = operations[1]
        assert isinstance(parent_op, WriteRelationship)
        assert parent_op.resource_type == ResourceType.WORKSPACE
        assert parent_op.resource_id == "01WORKSPACE_CHILD"
        assert parent_op.relation == RelationType.PARENT
        assert parent_op.subject_type == ResourceType.WORKSPACE
        assert parent_op.subject_id == "01WORKSPACE_ROOT"


class TestIAMEventTranslatorWorkspaceDeleted:
    """Tests for WorkspaceDeleted translation."""

    def test_translate_workspace_deleted_root_workspace(self):
        """Root workspace deletion should delete tenant and root_workspace relationships."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_ROOT",
            "tenant_id": "01TENANT_ABC",
            "parent_workspace_id": None,
            "is_root": True,
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceDeleted", payload)

        assert len(operations) == 2

        # First: delete workspace#tenant@tenant
        tenant_op = operations[0]
        assert isinstance(tenant_op, DeleteRelationship)
        assert tenant_op.resource_type == ResourceType.WORKSPACE
        assert tenant_op.resource_id == "01WORKSPACE_ROOT"
        assert tenant_op.relation == RelationType.TENANT
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == "01TENANT_ABC"

        # Second: delete tenant#root_workspace@workspace
        root_op = operations[1]
        assert isinstance(root_op, DeleteRelationship)
        assert root_op.resource_type == ResourceType.TENANT
        assert root_op.resource_id == "01TENANT_ABC"
        assert root_op.relation == RelationType.ROOT_WORKSPACE
        assert root_op.subject_type == ResourceType.WORKSPACE
        assert root_op.subject_id == "01WORKSPACE_ROOT"

    def test_translate_workspace_deleted_child_workspace(self):
        """Child workspace deletion should delete tenant and parent relationships."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_CHILD",
            "tenant_id": "01TENANT_ABC",
            "parent_workspace_id": "01WORKSPACE_ROOT",
            "is_root": False,
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceDeleted", payload)

        assert len(operations) == 2

        # First: delete workspace#tenant@tenant
        tenant_op = operations[0]
        assert isinstance(tenant_op, DeleteRelationship)
        assert tenant_op.resource_type == ResourceType.WORKSPACE
        assert tenant_op.resource_id == "01WORKSPACE_CHILD"
        assert tenant_op.relation == RelationType.TENANT
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == "01TENANT_ABC"

        # Second: delete workspace#parent@workspace
        parent_op = operations[1]
        assert isinstance(parent_op, DeleteRelationship)
        assert parent_op.resource_type == ResourceType.WORKSPACE
        assert parent_op.resource_id == "01WORKSPACE_CHILD"
        assert parent_op.relation == RelationType.PARENT
        assert parent_op.subject_type == ResourceType.WORKSPACE
        assert parent_op.subject_id == "01WORKSPACE_ROOT"


class TestIAMEventTranslatorWorkspaceMemberAdded:
    """Tests for WorkspaceMemberAdded translation."""

    def test_translates_user_member_added_to_workspace(self):
        """WorkspaceMemberAdded with USER type should write user role relationship."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_ABC",
            "member_id": "user-alice",
            "member_type": "user",
            "role": "editor",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceMemberAdded", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, WriteRelationship)
        assert op.resource_type == ResourceType.WORKSPACE
        assert op.resource_id == "01WORKSPACE_ABC"
        assert op.relation == WorkspaceRole.EDITOR
        assert op.subject_type == ResourceType.USER
        assert op.subject_id == "user-alice"

    def test_translates_group_member_added_to_workspace(self):
        """WorkspaceMemberAdded with GROUP type should write group role relationship."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_ABC",
            "member_id": "01GROUP_ENG",
            "member_type": "group",
            "role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceMemberAdded", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, WriteRelationship)
        assert op.resource_type == ResourceType.WORKSPACE
        assert op.resource_id == "01WORKSPACE_ABC"
        assert op.relation == WorkspaceRole.ADMIN
        assert op.subject_type == ResourceType.GROUP
        assert op.subject_id == "01GROUP_ENG"


class TestIAMEventTranslatorWorkspaceMemberRemoved:
    """Tests for WorkspaceMemberRemoved translation."""

    def test_translates_user_member_removed_from_workspace(self):
        """WorkspaceMemberRemoved with USER type should delete user role relationship."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_ABC",
            "member_id": "user-alice",
            "member_type": "user",
            "role": "member",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceMemberRemoved", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, DeleteRelationship)
        assert op.resource_type == ResourceType.WORKSPACE
        assert op.resource_id == "01WORKSPACE_ABC"
        assert op.relation == WorkspaceRole.MEMBER
        assert op.subject_type == ResourceType.USER
        assert op.subject_id == "user-alice"

    def test_translates_group_member_removed_from_workspace(self):
        """WorkspaceMemberRemoved with GROUP type should delete group role relationship."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_ABC",
            "member_id": "01GROUP_ENG",
            "member_type": "group",
            "role": "editor",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceMemberRemoved", payload)

        assert len(operations) == 1
        op = operations[0]
        assert isinstance(op, DeleteRelationship)
        assert op.resource_type == ResourceType.WORKSPACE
        assert op.resource_id == "01WORKSPACE_ABC"
        assert op.relation == WorkspaceRole.EDITOR
        assert op.subject_type == ResourceType.GROUP
        assert op.subject_id == "01GROUP_ENG"


class TestIAMEventTranslatorWorkspaceMemberRoleChanged:
    """Tests for WorkspaceMemberRoleChanged translation."""

    def test_translates_workspace_member_role_changed(self):
        """WorkspaceMemberRoleChanged should delete old role and write new role."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_ABC",
            "member_id": "user-alice",
            "member_type": "user",
            "old_role": "member",
            "new_role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceMemberRoleChanged", payload)

        assert len(operations) == 2

        # First should delete old role
        delete_op = operations[0]
        assert isinstance(delete_op, DeleteRelationship)
        assert delete_op.resource_type == ResourceType.WORKSPACE
        assert delete_op.resource_id == "01WORKSPACE_ABC"
        assert delete_op.relation == WorkspaceRole.MEMBER
        assert delete_op.subject_type == ResourceType.USER
        assert delete_op.subject_id == "user-alice"

        # Second should write new role
        write_op = operations[1]
        assert isinstance(write_op, WriteRelationship)
        assert write_op.resource_type == ResourceType.WORKSPACE
        assert write_op.resource_id == "01WORKSPACE_ABC"
        assert write_op.relation == WorkspaceRole.ADMIN
        assert write_op.subject_type == ResourceType.USER
        assert write_op.subject_id == "user-alice"

    def test_translates_group_workspace_member_role_changed(self):
        """WorkspaceMemberRoleChanged with GROUP type should use group subject type."""
        translator = IAMEventTranslator()
        payload = {
            "workspace_id": "01WORKSPACE_ABC",
            "member_id": "01GROUP_ENG",
            "member_type": "group",
            "old_role": "editor",
            "new_role": "admin",
            "occurred_at": "2026-01-08T12:00:00+00:00",
        }

        operations = translator.translate("WorkspaceMemberRoleChanged", payload)

        assert len(operations) == 2

        # Both should use GROUP subject type
        for op in operations:
            assert op.subject_type == ResourceType.GROUP
            assert op.subject_id == "01GROUP_ENG"


class TestIAMEventTranslatorErrors:
    """Tests for error handling."""

    def test_raises_on_unsupported_event_type(self):
        """Translator should raise ValueError for unknown event types."""
        translator = IAMEventTranslator()

        with pytest.raises(ValueError) as exc_info:
            translator.translate("UnknownEvent", {})

        assert "Unknown event type" in str(exc_info.value)
