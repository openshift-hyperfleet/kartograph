"""Unit tests for UserRepository.

Following TDD principles - tests verify user repository behavior with mocked dependencies.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from unittest.mock import AsyncMock, MagicMock

from iam.domain.aggregates import User
from iam.domain.value_objects import UserId
from iam.infrastructure.models import UserModel
from iam.infrastructure.user_repository import UserRepository
from iam.ports.exceptions import ProvisioningConflictError
from iam.ports.repositories import IUserRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def repository(mock_session):
    """Create repository with mock session."""
    return UserRepository(session=mock_session)


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_implements_protocol(self, repository):
        """Repository should implement IUserRepository protocol."""
        assert isinstance(repository, IUserRepository)


class TestSave:
    """Tests for save method."""

    @pytest.mark.asyncio
    async def test_translates_integrity_error_to_provisioning_conflict(
        self, repository, mock_session
    ):
        """Should raise ProvisioningConflictError (not IntegrityError) on duplicate username.

        This ensures database internals are not exposed to callers.
        session.add() is synchronous on AsyncSession, so we use MagicMock for it.
        """
        user = User(id=UserId.generate(), username="alice")

        # Session returns None on the existence check (no existing user by id)
        # but then raises IntegrityError when the new model is added.
        # session.add() is sync on AsyncSession → use MagicMock (not AsyncMock).
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock(
            side_effect=IntegrityError(
                statement="INSERT INTO users",
                params={},
                orig=Exception(
                    'duplicate key value violates unique constraint "users_username_key"'
                ),
            )
        )

        with pytest.raises(ProvisioningConflictError) as exc_info:
            await repository.save(user)

        assert exc_info.value.username == "alice"

    @pytest.mark.asyncio
    async def test_does_not_swallow_non_integrity_errors(
        self, repository, mock_session
    ):
        """Should propagate non-IntegrityError exceptions unchanged."""
        user = User(id=UserId.generate(), username="alice")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        # session.add() is sync on AsyncSession → use MagicMock (not AsyncMock).
        mock_session.add = MagicMock(side_effect=RuntimeError("Unexpected DB error"))

        with pytest.raises(RuntimeError, match="Unexpected DB error"):
            await repository.save(user)

    @pytest.mark.asyncio
    async def test_adds_new_user_to_session(self, repository, mock_session):
        """Should add new user model to session."""
        user = User(
            id=UserId.generate(),
            username="alice",
        )

        # Mock session to return None (user doesn't exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(user)

        # Should add new model
        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        assert isinstance(added_model, UserModel)
        assert added_model.id == user.id.value
        assert added_model.username == user.username

    @pytest.mark.asyncio
    async def test_updates_existing_user(self, repository, mock_session):
        """Should update existing user model."""
        user_id = UserId.generate()
        user = User(
            id=user_id,
            username="alice_updated",
        )

        # Mock existing user
        existing_model = UserModel(id=user_id.value, username="alice")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute.return_value = mock_result

        await repository.save(user)

        # Should not add, should update
        mock_session.add.assert_not_called()
        assert existing_model.username == "alice_updated"


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, repository, mock_session):
        """Should return None when user doesn't exist."""
        user_id = UserId.generate()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(user_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_when_found(self, repository, mock_session):
        """Should return user when found."""
        user_id = UserId.generate()
        model = UserModel(id=user_id.value, username="alice")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(user_id)

        assert result is not None
        assert result.id.value == user_id.value
        assert result.username == "alice"


class TestGetByUsername:
    """Tests for get_by_username method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, repository, mock_session):
        """Should return None when username doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_username("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_by_username(self, repository, mock_session):
        """Should return user when found by username."""
        user_id = UserId.generate()
        model = UserModel(id=user_id.value, username="alice")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_username("alice")

        assert result is not None
        assert result.username == "alice"
        assert result.id.value == user_id.value
