"""Integration tests for UserRepository.

These tests require PostgreSQL to be running.
They verify user metadata persistence and retrieval.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from iam.domain.aggregates import User
from iam.domain.value_objects import UserId
from iam.infrastructure.user_repository import UserRepository

pytestmark = pytest.mark.integration


class TestUserRoundTrip:
    """Tests for save and retrieve operations."""

    @pytest.mark.asyncio
    async def test_saves_and_retrieves_user(
        self, user_repository: UserRepository, async_session, clean_iam_data
    ):
        """Should save user to PostgreSQL and retrieve it."""
        user = User(
            id=UserId.generate(),
            username="alice",
        )

        async with async_session.begin():
            await user_repository.save(user)

        # Retrieve the user
        retrieved = await user_repository.get_by_id(user.id)

        assert retrieved is not None
        assert retrieved.id.value == user.id.value
        assert retrieved.username == user.username

    @pytest.mark.asyncio
    async def test_updates_existing_user(
        self, user_repository: UserRepository, async_session, clean_iam_data
    ):
        """Should update existing user's username."""
        user = User(id=UserId.generate(), username="alice")

        # Save initial user
        async with async_session.begin():
            await user_repository.save(user)

        # Update username
        user = User(id=user.id, username="alice_smith")
        async with async_session.begin():
            await user_repository.save(user)

        # Verify update
        retrieved = await user_repository.get_by_id(user.id)
        assert retrieved is not None
        assert retrieved.username == "alice_smith"


class TestGetByUsername:
    """Tests for retrieving users by username."""

    @pytest.mark.asyncio
    async def test_retrieves_user_by_username(
        self, user_repository: UserRepository, async_session, clean_iam_data
    ):
        """Should retrieve user by username."""
        user = User(id=UserId.generate(), username="alice")

        async with async_session.begin():
            await user_repository.save(user)

        # Retrieve by username
        retrieved = await user_repository.get_by_username("alice")

        assert retrieved is not None
        assert retrieved.id.value == user.id.value
        assert retrieved.username == "alice"

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_username(
        self, user_repository: UserRepository, async_session, clean_iam_data
    ):
        """Should return None when username doesn't exist."""
        retrieved = await user_repository.get_by_username("nonexistent")

        assert retrieved is None


class TestUsernameUniqueness:
    """Tests for username uniqueness constraint."""

    @pytest.mark.asyncio
    async def test_duplicate_username_raises_error(
        self, user_repository: UserRepository, async_session, clean_iam_data
    ):
        """Should raise IntegrityError for duplicate username."""
        user1 = User(id=UserId.generate(), username="alice")

        # Save first user
        async with async_session.begin():
            await user_repository.save(user1)

        # Try to save another user with same username
        user2 = User(id=UserId.generate(), username="alice")

        with pytest.raises(IntegrityError):
            async with async_session.begin():
                await user_repository.save(user2)
