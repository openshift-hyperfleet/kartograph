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
