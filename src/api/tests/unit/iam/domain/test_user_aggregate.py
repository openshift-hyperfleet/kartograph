"""Unit tests for User aggregate (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the User aggregate to make these tests pass.
"""

import pytest

from iam.domain.aggregates import User
from iam.domain.value_objects import UserId


class TestUserCreation:
    """Tests for User aggregate creation."""

    def test_creates_with_required_fields(self):
        """Test that User can be created with required fields."""
        user_id = UserId.generate()

        user = User(
            id=user_id,
            username="alice",
        )

        assert user.id == user_id
        assert user.username == "alice"

    def test_requires_id(self):
        """Test that User requires an id."""
        with pytest.raises(TypeError):
            User(username="alice")

    def test_requires_username(self):
        """Test that User requires a username."""
        with pytest.raises(TypeError):
            User(id=UserId.generate())

    def test_username_is_immutable(self):
        """Test that username cannot be changed after creation."""
        user = User(
            id=UserId.generate(),
            username="alice",
        )

        # Dataclass should be frozen
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            user.username = "bob"


class TestUserEquality:
    """Tests for User equality based on identity."""

    def test_users_equal_when_same_id(self):
        """Test that users with same ID are considered equal."""
        user_id = UserId.generate()
        user1 = User(id=user_id, username="alice")
        user2 = User(id=user_id, username="alice")

        assert user1 == user2

    def test_users_not_equal_when_different_id(self):
        """Test that users with different IDs are not equal."""
        user1 = User(id=UserId.generate(), username="alice")
        user2 = User(id=UserId.generate(), username="alice")

        assert user1 != user2


class TestUserStringRepresentation:
    """Tests for User string representation."""

    def test_str_includes_username(self):
        """Test that string representation includes username."""
        user = User(
            id=UserId.generate(),
            username="alice",
        )

        str_repr = str(user)

        assert "alice" in str_repr


class TestExternalIdentityFormat:
    """Tests for Requirement: External Identity Format.

    The system SHALL accept arbitrary external identity formats from the
    identity provider.
    """

    def test_accepts_uuid_format_subject_identifier(self):
        """Should store UUID-format external identity as-is (not converted to ULID).

        Scenario: UUID-format identity
        GIVEN an identity provider that uses UUID-format subject identifiers
        WHEN the user authenticates
        THEN the identifier is stored as-is (not converted to ULID)
        """
        uuid_sub = "550e8400-e29b-41d4-a716-446655440000"
        user_id = UserId(value=uuid_sub)
        user = User(id=user_id, username="alice")

        assert user.id.value == uuid_sub

    def test_accepts_arbitrary_string_subject_identifier(self):
        """Should store arbitrary string external identities as-is."""
        arbitrary_sub = "auth0|5f7f8d6b234e7a001e8b4567"
        user_id = UserId(value=arbitrary_sub)
        user = User(id=user_id, username="alice")

        assert user.id.value == arbitrary_sub

    def test_user_id_is_not_restricted_to_ulid_format(self):
        """UserId should accept non-ULID values (external SSO IDs)."""
        # UUID format (not a ULID)
        uuid_id = UserId(value="550e8400-e29b-41d4-a716-446655440000")
        # Plain string format
        str_id = UserId(value="github|12345")

        assert uuid_id.value == "550e8400-e29b-41d4-a716-446655440000"
        assert str_id.value == "github|12345"


class TestMultiTenantAccess:
    """Tests for Requirement: Multi-Tenant Access.

    The system SHALL allow a single user to be a member of multiple tenants.
    """

    def test_user_aggregate_has_no_tenant_field(self):
        """User aggregate must not be restricted to a single tenant.

        Tenant membership is managed separately (via SpiceDB relationships)
        so the User aggregate itself must not carry a tenant_id. This ensures
        a single user identity can be a member of multiple tenants.
        """
        user = User(id=UserId(value="user-123"), username="alice")
        assert not hasattr(user, "tenant_id")

    def test_same_user_identity_is_reusable_across_tenants(self):
        """The same UserId can reference the same user in different tenant contexts.

        This test confirms that User is a tenant-agnostic identity — tenant
        membership is expressed externally (SpiceDB), not embedded in the aggregate.
        """
        user_id = UserId(value="user-abc-123")

        # The same user identity can appear in multiple tenant contexts
        user_in_tenant_a = User(id=user_id, username="alice")
        user_in_tenant_b = User(id=user_id, username="alice")

        # Same identity — the user is the same person regardless of tenant
        assert user_in_tenant_a == user_in_tenant_b
        assert user_in_tenant_a.id == user_in_tenant_b.id
