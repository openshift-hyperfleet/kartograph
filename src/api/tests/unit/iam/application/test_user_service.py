"""Unit tests for UserService.

Following TDD - write tests first to define desired behavior.
"""

import pytest
from unittest.mock import AsyncMock, create_autospec

from iam.domain.aggregates import User
from iam.domain.value_objects import UserId
from iam.ports.repositories import IUserRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
    return AsyncMock()


@pytest.fixture
def mock_user_repository():
    """Create mock user repository."""
    return create_autospec(IUserRepository, instance=True)


@pytest.fixture
def mock_probe():
    """Create mock user service probe."""
    from iam.application.observability import UserServiceProbe

    return create_autospec(UserServiceProbe, instance=True)


@pytest.fixture
def user_service(mock_user_repository, mock_session, mock_probe):
    """Create UserService with mock dependencies."""
    from iam.application.services.user_service import UserService

    return UserService(
        user_repository=mock_user_repository,
        session=mock_session,
        probe=mock_probe,
    )


class TestUserServiceInit:
    """Tests for UserService initialization."""

    def test_stores_repository(self, mock_user_repository, mock_session):
        """Service should store repository reference."""
        from iam.application.services.user_service import UserService

        service = UserService(
            user_repository=mock_user_repository,
            session=mock_session,
        )
        assert service._user_repository is mock_user_repository

    def test_uses_default_probe_when_not_provided(
        self, mock_user_repository, mock_session
    ):
        """Service should create default probe when not provided."""
        from iam.application.services.user_service import UserService

        service = UserService(
            user_repository=mock_user_repository,
            session=mock_session,
        )
        assert service._probe is not None


class TestEnsureUser:
    """Tests for ensure_user method."""

    @pytest.mark.asyncio
    async def test_returns_existing_user(
        self, user_service, mock_user_repository, mock_probe
    ):
        """Should return existing user if found in repository."""
        user_id = UserId.generate()
        existing_user = User(id=user_id, username="alice")

        mock_user_repository.get_by_id = AsyncMock(return_value=existing_user)

        result = await user_service.ensure_user(user_id, "alice")

        assert result == existing_user
        mock_user_repository.save.assert_not_called()
        mock_probe.user_ensured.assert_called_once_with(
            user_id=user_id.value,
            username="alice",
            was_created=False,
            was_updated=False,
        )

    @pytest.mark.asyncio
    async def test_creates_new_user_when_not_found(
        self, user_service, mock_user_repository, mock_probe
    ):
        """Should create new user if not found in repository."""
        user_id = UserId.generate()

        mock_user_repository.get_by_id = AsyncMock(return_value=None)
        mock_user_repository.save = AsyncMock()

        result = await user_service.ensure_user(user_id, "bob")

        assert result.id == user_id
        assert result.username == "bob"
        mock_user_repository.save.assert_called_once()
        saved_user = mock_user_repository.save.call_args[0][0]
        assert saved_user.id == user_id
        assert saved_user.username == "bob"
        mock_probe.user_ensured.assert_called_once_with(
            user_id=user_id.value,
            username="bob",
            was_created=True,
            was_updated=False,
        )

    @pytest.mark.asyncio
    async def test_syncs_username_when_changed(
        self, user_service, mock_user_repository, mock_probe
    ):
        """Should update username if changed in SSO."""
        user_id = UserId.generate()
        existing_user = User(id=user_id, username="alice_old")

        mock_user_repository.get_by_id = AsyncMock(return_value=existing_user)
        mock_user_repository.save = AsyncMock()

        result = await user_service.ensure_user(user_id, "alice_new")

        assert result.username == "alice_new"
        mock_user_repository.save.assert_called_once()
        saved_user = mock_user_repository.save.call_args[0][0]
        assert saved_user.username == "alice_new"
        mock_probe.user_ensured.assert_called_once_with(
            user_id=user_id.value,
            username="alice_new",
            was_created=False,
            was_updated=True,
        )

    @pytest.mark.asyncio
    async def test_records_failure_on_exception(
        self, user_service, mock_user_repository, mock_probe
    ):
        """Should record probe event when provisioning fails."""
        user_id = UserId.generate()

        mock_user_repository.get_by_id = AsyncMock(return_value=None)
        mock_user_repository.save = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(Exception):
            await user_service.ensure_user(user_id, "charlie")

        mock_probe.user_provision_failed.assert_called_once()
        call_args = mock_probe.user_provision_failed.call_args[1]
        assert call_args["user_id"] == user_id.value
        assert call_args["username"] == "charlie"
        assert "DB error" in call_args["error"]
