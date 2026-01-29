"""Unit tests for IAMEventTranslator (TDD - tests first).

These tests verify that IAM domain events are correctly translated into
SpiceDB relationship operations using type-safe enums.
"""

import pytest

from iam.domain.value_objects import GroupRole
from iam.infrastructure.outbox import IAMEventTranslator
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import DeleteRelationship, WriteRelationship


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


class TestIAMEventTranslatorErrors:
    """Tests for error handling."""

    def test_raises_on_unsupported_event_type(self):
        """Translator should raise ValueError for unknown event types."""
        translator = IAMEventTranslator()

        with pytest.raises(ValueError) as exc_info:
            translator.translate("UnknownEvent", {})

        assert "Unsupported event type" in str(exc_info.value)
