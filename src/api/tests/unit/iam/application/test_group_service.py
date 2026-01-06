"""Unit tests for GroupService.

Following TDD - write tests first to define desired behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, create_autospec

from iam.domain.aggregates import Group, User
from iam.domain.value_objects import Role, TenantId, UserId
from iam.ports.exceptions import DuplicateGroupNameError
from iam.ports.repositories import IGroupRepository


@pytest.fixture
def mock_session():
    """Create mock async session with transaction support."""
    session = AsyncMock()
    # Mock transaction context manager properly
    mock_transaction = MagicMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=None)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=mock_transaction)
    return session


@pytest.fixture
def mock_group_repository():
    """Create mock group repository."""
    return create_autospec(IGroupRepository, instance=True)


@pytest.fixture
def mock_user_service():
    """Create mock user service."""
    from iam.application.services.user_service import UserService

    return create_autospec(UserService, instance=True)


@pytest.fixture
def mock_probe():
    """Create mock group service probe."""
    from iam.application.observability import GroupServiceProbe

    return create_autospec(GroupServiceProbe, instance=True)


@pytest.fixture
def group_service(mock_session, mock_group_repository, mock_user_service, mock_probe):
    """Create GroupService with mock dependencies."""
    from iam.application.services.group_service import GroupService

    return GroupService(
        session=mock_session,
        group_repository=mock_group_repository,
        user_service=mock_user_service,
        probe=mock_probe,
    )


class TestGroupServiceInit:
    """Tests for GroupService initialization."""

    def test_stores_session(
        self, mock_session, mock_group_repository, mock_user_service
    ):
        """Service should store session reference."""
        from iam.application.services.group_service import GroupService

        service = GroupService(
            session=mock_session,
            group_repository=mock_group_repository,
            user_service=mock_user_service,
        )
        assert service._session is mock_session

    def test_stores_repository(
        self, mock_session, mock_group_repository, mock_user_service
    ):
        """Service should store repository reference."""
        from iam.application.services.group_service import GroupService

        service = GroupService(
            session=mock_session,
            group_repository=mock_group_repository,
            user_service=mock_user_service,
        )
        assert service._group_repository is mock_group_repository

    def test_stores_user_service(
        self, mock_session, mock_group_repository, mock_user_service
    ):
        """Service should store user service reference."""
        from iam.application.services.group_service import GroupService

        service = GroupService(
            session=mock_session,
            group_repository=mock_group_repository,
            user_service=mock_user_service,
        )
        assert service._user_service is mock_user_service

    def test_uses_default_probe_when_not_provided(
        self, mock_session, mock_group_repository, mock_user_service
    ):
        """Service should create default probe when not provided."""
        from iam.application.services.group_service import GroupService

        service = GroupService(
            session=mock_session,
            group_repository=mock_group_repository,
            user_service=mock_user_service,
        )
        assert service._probe is not None


class TestCreateGroup:
    """Tests for create_group method."""

    @pytest.mark.asyncio
    async def test_ensures_creator_exists(
        self, group_service, mock_user_service, mock_probe
    ):
        """Should ensure creator user exists before creating group."""
        creator_id = UserId.generate()
        tenant_id = TenantId.generate()
        creator = User(id=creator_id, username="alice")

        mock_user_service.ensure_user = AsyncMock(return_value=creator)

        await group_service.create_group(
            name="Engineering",
            creator_id=creator_id,
            creator_username="alice",
            tenant_id=tenant_id,
        )

        mock_user_service.ensure_user.assert_called_once_with(creator_id, "alice")

    @pytest.mark.asyncio
    async def test_creates_group_with_creator_as_admin(
        self, group_service, mock_user_service, mock_group_repository
    ):
        """Should create group with creator as admin member."""
        creator_id = UserId.generate()
        tenant_id = TenantId.generate()
        creator = User(id=creator_id, username="alice")

        mock_user_service.ensure_user = AsyncMock(return_value=creator)
        mock_group_repository.save = AsyncMock()

        result = await group_service.create_group(
            name="Engineering",
            creator_id=creator_id,
            creator_username="alice",
            tenant_id=tenant_id,
        )

        # Verify group was created
        assert isinstance(result, Group)
        assert result.name == "Engineering"
        assert len(result.members) == 1
        assert result.members[0].user_id == creator_id
        assert result.members[0].role == Role.ADMIN

    @pytest.mark.asyncio
    async def test_saves_group_to_repository(
        self, group_service, mock_user_service, mock_group_repository
    ):
        """Should save group via repository."""
        creator_id = UserId.generate()
        tenant_id = TenantId.generate()
        creator = User(id=creator_id, username="alice")

        mock_user_service.ensure_user = AsyncMock(return_value=creator)
        mock_group_repository.save = AsyncMock()

        await group_service.create_group(
            name="Engineering",
            creator_id=creator_id,
            creator_username="alice",
            tenant_id=tenant_id,
        )

        # Verify save was called with tenant_id
        mock_group_repository.save.assert_called_once()
        saved_group, saved_tenant_id = mock_group_repository.save.call_args[0]
        assert saved_group.name == "Engineering"
        assert saved_tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_records_success_probe_event(
        self, group_service, mock_user_service, mock_probe
    ):
        """Should record group_created probe event on success."""
        creator_id = UserId.generate()
        tenant_id = TenantId.generate()
        creator = User(id=creator_id, username="alice")

        mock_user_service.ensure_user = AsyncMock(return_value=creator)

        result = await group_service.create_group(
            name="Engineering",
            creator_id=creator_id,
            creator_username="alice",
            tenant_id=tenant_id,
        )

        mock_probe.group_created.assert_called_once()
        call_args = mock_probe.group_created.call_args[1]
        assert call_args["group_id"] == result.id.value
        assert call_args["name"] == "Engineering"
        assert call_args["tenant_id"] == tenant_id.value
        assert call_args["creator_id"] == creator_id.value

    @pytest.mark.asyncio
    async def test_records_failure_probe_event(
        self, group_service, mock_user_service, mock_group_repository, mock_probe
    ):
        """Should record group_creation_failed probe event on error."""
        creator_id = UserId.generate()
        tenant_id = TenantId.generate()
        creator = User(id=creator_id, username="alice")

        mock_user_service.ensure_user = AsyncMock(return_value=creator)
        mock_group_repository.save = AsyncMock(
            side_effect=DuplicateGroupNameError("Name exists")
        )

        with pytest.raises(DuplicateGroupNameError):
            await group_service.create_group(
                name="Engineering",
                creator_id=creator_id,
                creator_username="alice",
                tenant_id=tenant_id,
            )

        mock_probe.group_creation_failed.assert_called_once()
        call_args = mock_probe.group_creation_failed.call_args[1]
        assert call_args["name"] == "Engineering"
        assert call_args["tenant_id"] == tenant_id.value
        assert "Name exists" in call_args["error"]
