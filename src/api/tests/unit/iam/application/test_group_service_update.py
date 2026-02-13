"""Unit tests for GroupService.update_group() (rename).

Tests the application service layer for renaming groups with
MANAGE permission check and name uniqueness validation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from iam.application.services.group_service import GroupService
from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, TenantId, UserId
from iam.ports.exceptions import DuplicateGroupNameError
from iam.ports.repositories import IGroupRepository


@pytest.fixture
def mock_session():
    """Create mock async session with transaction support."""
    session = AsyncMock()
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
def mock_authz():
    """Create mock authorization provider."""
    from shared_kernel.authorization.protocols import AuthorizationProvider

    return create_autospec(AuthorizationProvider, instance=True)


@pytest.fixture
def mock_probe():
    """Create mock group service probe."""
    from iam.application.observability.group_service_probe import GroupServiceProbe

    return create_autospec(GroupServiceProbe, instance=True)


@pytest.fixture
def tenant_id() -> TenantId:
    return TenantId.generate()


@pytest.fixture
def group_service(
    mock_session,
    mock_group_repository,
    mock_authz,
    mock_probe,
    tenant_id,
):
    """Create GroupService with mock dependencies."""
    return GroupService(
        session=mock_session,
        group_repository=mock_group_repository,
        authz=mock_authz,
        scope_to_tenant=tenant_id,
        probe=mock_probe,
    )


class TestUpdateGroup:
    """Tests for GroupService.update_group()."""

    @pytest.mark.asyncio
    async def test_renames_group_with_manage_permission(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Should rename group when user has MANAGE permission."""
        group_id = GroupId.generate()
        user_id = UserId.generate()
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering",
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_group_repository.get_by_name = AsyncMock(return_value=None)
        mock_group_repository.save = AsyncMock()

        result = await group_service.update_group(
            group_id=group_id,
            user_id=user_id,
            name="Platform Engineering",
        )

        assert result.name == "Platform Engineering"
        mock_group_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_permission_error_without_manage(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Should raise PermissionError when user lacks MANAGE permission."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission"):
            await group_service.update_group(
                group_id=group_id,
                user_id=user_id,
                name="New Name",
            )

    @pytest.mark.asyncio
    async def test_raises_value_error_when_group_not_found(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
    ):
        """Should raise ValueError when group doesn't exist."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await group_service.update_group(
                group_id=group_id,
                user_id=user_id,
                name="New Name",
            )

    @pytest.mark.asyncio
    async def test_raises_value_error_when_tenant_mismatch(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
    ):
        """Should raise ValueError when group belongs to different tenant."""
        group_id = GroupId.generate()
        user_id = UserId.generate()
        other_tenant = TenantId.generate()
        group = Group(
            id=group_id,
            tenant_id=other_tenant,
            name="Engineering",
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)

        with pytest.raises(ValueError, match="different tenant"):
            await group_service.update_group(
                group_id=group_id,
                user_id=user_id,
                name="New Name",
            )

    @pytest.mark.asyncio
    async def test_raises_duplicate_name_error_when_name_exists(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Should raise DuplicateGroupNameError when name already exists."""
        group_id = GroupId.generate()
        user_id = UserId.generate()
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering",
        )
        existing_group = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Platform Engineering",
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_group_repository.get_by_name = AsyncMock(return_value=existing_group)

        with pytest.raises(DuplicateGroupNameError):
            await group_service.update_group(
                group_id=group_id,
                user_id=user_id,
                name="Platform Engineering",
            )

    @pytest.mark.asyncio
    async def test_skips_uniqueness_check_when_name_unchanged(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Should skip uniqueness check if name hasn't changed."""
        group_id = GroupId.generate()
        user_id = UserId.generate()
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering",
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_group_repository.save = AsyncMock()

        # Same name should still work (no-op rename) - the aggregate
        # may raise ValueError for unchanged name; that's acceptable.
        # The service should NOT check get_by_name if name is unchanged.
        await group_service.update_group(
            group_id=group_id,
            user_id=user_id,
            name="Engineering",
        )

        mock_group_repository.get_by_name.assert_not_called()
