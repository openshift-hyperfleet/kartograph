"""Unit tests for SpiceDB operation value objects.

These tests verify the operation dataclasses and their computed properties.
"""

from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    SpiceDBRelationshipBase,
    WriteRelationship,
)


class TestSpiceDBRelationshipBase:
    """Tests for the base class shared properties."""

    def test_write_relationship_inherits_from_base(self):
        """WriteRelationship should inherit from SpiceDBRelationshipBase."""
        op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )
        assert isinstance(op, SpiceDBRelationshipBase)

    def test_delete_relationship_inherits_from_base(self):
        """DeleteRelationship should inherit from SpiceDBRelationshipBase."""
        op = DeleteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )
        assert isinstance(op, SpiceDBRelationshipBase)


class TestWriteRelationship:
    """Tests for WriteRelationship value object."""

    def test_resource_property(self):
        """Should format resource as type:id."""
        op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )
        assert op.resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"

    def test_subject_property(self):
        """Should format subject as type:id."""
        op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )
        assert op.subject == "tenant:01ARZCX0P0HZGQP3MZXQQ0NNYY"

    def test_relation_name_property_with_enum(self):
        """Should convert relation enum to string."""
        op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )
        assert op.relation_name == "tenant"

    def test_relation_name_property_with_role_string(self):
        """Should handle role strings (from Role enum)."""
        from iam.domain.value_objects import GroupRole

        op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=GroupRole.ADMIN,
            subject_type=ResourceType.USER,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
        )
        assert op.relation_name == "admin"

    def test_is_frozen(self):
        """WriteRelationship should be immutable."""
        op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )
        try:
            op.resource_id = "new_id"  # type: ignore
            assert False, "Should have raised FrozenInstanceError"
        except Exception:
            pass  # Expected


class TestSubjectRelation:
    """Tests for the optional subject_relation field and subject property."""

    def test_subject_without_relation_returns_type_colon_id(self):
        """Subject property should return 'type:id' when no subject_relation."""
        op = WriteRelationship(
            resource_type=ResourceType.WORKSPACE,
            resource_id="01WORKSPACE_ABC",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="user-alice",
        )
        assert op.subject_relation is None
        assert op.subject == "user:user-alice"

    def test_subject_with_relation_returns_type_colon_id_hash_relation(self):
        """Subject property should return 'type:id#relation' when subject_relation is set."""
        op = WriteRelationship(
            resource_type=ResourceType.WORKSPACE,
            resource_id="01WORKSPACE_ABC",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.GROUP,
            subject_id="01GROUP_ENG",
            subject_relation="member",
        )
        assert op.subject_relation == "member"
        assert op.subject == "group:01GROUP_ENG#member"

    def test_delete_relationship_subject_with_relation(self):
        """DeleteRelationship should also support subject_relation."""
        op = DeleteRelationship(
            resource_type=ResourceType.WORKSPACE,
            resource_id="01WORKSPACE_ABC",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.GROUP,
            subject_id="01GROUP_ENG",
            subject_relation="member",
        )
        assert op.subject == "group:01GROUP_ENG#member"

    def test_delete_relationship_subject_without_relation(self):
        """DeleteRelationship without subject_relation returns 'type:id'."""
        op = DeleteRelationship(
            resource_type=ResourceType.WORKSPACE,
            resource_id="01WORKSPACE_ABC",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="user-alice",
        )
        assert op.subject_relation is None
        assert op.subject == "user:user-alice"

    def test_subject_relation_defaults_to_none(self):
        """subject_relation should default to None when not provided."""
        op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNYY",
        )
        assert op.subject_relation is None

    def test_subject_relation_is_frozen(self):
        """subject_relation should be immutable like other fields."""
        op = WriteRelationship(
            resource_type=ResourceType.WORKSPACE,
            resource_id="01WORKSPACE_ABC",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.GROUP,
            subject_id="01GROUP_ENG",
            subject_relation="member",
        )
        try:
            op.subject_relation = "admin"  # type: ignore
            assert False, "Should have raised FrozenInstanceError"
        except Exception:
            pass  # Expected


class TestDeleteRelationship:
    """Tests for DeleteRelationship value object."""

    def test_resource_property(self):
        """Should format resource as type:id."""
        op = DeleteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
        )
        assert op.resource == "group:01ARZCX0P0HZGQP3MZXQQ0NNZZ"

    def test_subject_property(self):
        """Should format subject as type:id."""
        op = DeleteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
        )
        assert op.subject == "user:01ARZCX0P0HZGQP3MZXQQ0NNWW"

    def test_relation_name_property(self):
        """Should convert relation enum to string."""
        op = DeleteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
        )
        assert op.relation_name == "member"

    def test_is_frozen(self):
        """DeleteRelationship should be immutable."""
        op = DeleteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="01ARZCX0P0HZGQP3MZXQQ0NNZZ",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="01ARZCX0P0HZGQP3MZXQQ0NNWW",
        )
        try:
            op.resource_id = "new_id"  # type: ignore
            assert False, "Should have raised FrozenInstanceError"
        except Exception:
            pass  # Expected
