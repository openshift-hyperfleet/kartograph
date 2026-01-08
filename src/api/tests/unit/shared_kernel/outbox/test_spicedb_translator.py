"""Unit tests for SpiceDB translator (TDD - tests first).

These tests verify that domain events are correctly translated into
SpiceDB relationship operations.
"""

from datetime import UTC, datetime


from iam.domain.events import (
    GroupCreated,
    GroupDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
)
from iam.domain.value_objects import Role
from shared_kernel.outbox.spicedb_translator import (
    DeleteAllRelationships,
    DeleteRelationship,
    SpiceDBOperation,
    SpiceDBTranslator,
    WriteRelationship,
)


class TestSpiceDBOperations:
    """Tests for SpiceDB operation value objects."""

    def test_write_relationship_is_immutable(self):
        """Test that WriteRelationship is immutable."""
        op = WriteRelationship(
            resource="group:01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation="tenant",
            subject="tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )

        assert op.resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert op.relation == "tenant"
        assert op.subject == "tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_delete_relationship_is_immutable(self):
        """Test that DeleteRelationship is immutable."""
        op = DeleteRelationship(
            resource="group:01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation="member",
            subject="user:01ARZCX0P0HZGQP3MZXQQ0NNWW",
        )

        assert op.resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert op.relation == "member"
        assert op.subject == "user:01ARZCX0P0HZGQP3MZXQQ0NNWW"

    def test_delete_all_relationships_is_immutable(self):
        """Test that DeleteAllRelationships is immutable."""
        op = DeleteAllRelationships(
            resource="group:01ARZCX0P0HZGQP3MZXQQ0NNZZ",
        )

        assert op.resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"


class TestSpiceDBTranslator:
    """Tests for SpiceDBTranslator.translate() method."""

    def test_translates_group_created(self):
        """Test that GroupCreated produces tenant relationship write."""
        translator = SpiceDBTranslator()
        event = GroupCreated(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        operations = translator.translate(event)

        assert len(operations) == 1
        assert isinstance(operations[0], WriteRelationship)
        assert operations[0].resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[0].relation == "tenant"
        assert operations[0].subject == "tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_translates_group_deleted(self):
        """Test that GroupDeleted produces delete all relationships."""
        translator = SpiceDBTranslator()
        event = GroupDeleted(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            tenant_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        operations = translator.translate(event)

        assert len(operations) == 1
        assert isinstance(operations[0], DeleteAllRelationships)
        assert operations[0].resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"

    def test_translates_member_added_with_member_role(self):
        """Test that MemberAdded with MEMBER role produces member relationship."""
        translator = SpiceDBTranslator()
        event = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.MEMBER,
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        operations = translator.translate(event)

        assert len(operations) == 1
        assert isinstance(operations[0], WriteRelationship)
        assert operations[0].resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[0].relation == "member"
        assert operations[0].subject == "user:01ARZCX0P0HZGQP3MZXQQ0NNWW"

    def test_translates_member_added_with_admin_role(self):
        """Test that MemberAdded with ADMIN role produces admin relationship."""
        translator = SpiceDBTranslator()
        event = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.ADMIN,
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        operations = translator.translate(event)

        assert len(operations) == 1
        assert isinstance(operations[0], WriteRelationship)
        assert operations[0].relation == "admin"

    def test_translates_member_removed(self):
        """Test that MemberRemoved produces delete relationship."""
        translator = SpiceDBTranslator()
        event = MemberRemoved(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.MEMBER,
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        operations = translator.translate(event)

        assert len(operations) == 1
        assert isinstance(operations[0], DeleteRelationship)
        assert operations[0].resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        assert operations[0].relation == "member"
        assert operations[0].subject == "user:01ARZCX0P0HZGQP3MZXQQ0NNWW"

    def test_translates_member_role_changed(self):
        """Test that MemberRoleChanged produces delete + write operations."""
        translator = SpiceDBTranslator()
        event = MemberRoleChanged(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            old_role=Role.MEMBER,
            new_role=Role.ADMIN,
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        operations = translator.translate(event)

        assert len(operations) == 2

        # First operation should delete the old role
        assert isinstance(operations[0], DeleteRelationship)
        assert operations[0].relation == "member"

        # Second operation should write the new role
        assert isinstance(operations[1], WriteRelationship)
        assert operations[1].relation == "admin"

    def test_all_operations_use_correct_format(self):
        """Test that all operations use format_resource and format_subject."""
        translator = SpiceDBTranslator()
        event = MemberAdded(
            group_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            user_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
            role=Role.MEMBER,
            occurred_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        operations = translator.translate(event)

        # Verify format: "type:id"
        assert ":" in operations[0].resource
        assert ":" in operations[0].subject
        assert operations[0].resource.startswith("group:")
        assert operations[0].subject.startswith("user:")


class TestSpiceDBOperationUnion:
    """Tests for SpiceDBOperation type alias."""

    def test_all_operations_can_be_typed_as_spicedb_operation(self):
        """Test that all operation types can be used as SpiceDBOperation."""
        operations: list[SpiceDBOperation] = [
            WriteRelationship(
                resource="group:abc",
                relation="tenant",
                subject="tenant:xyz",
            ),
            DeleteRelationship(
                resource="group:abc",
                relation="member",
                subject="user:123",
            ),
            DeleteAllRelationships(
                resource="group:abc",
            ),
        ]

        assert len(operations) == 3
