"""Unit tests for GroupService member management methods.

Tests for add_member, remove_member, update_member_role, and list_members
with proper permission checks via SpiceDB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from iam.application.services.group_service import GroupService
from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, GroupRole, TenantId, UserId
from iam.ports.repositories import IGroupRepository
from shared_kernel.authorization.types import RelationshipTuple


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


class TestAddMember:
    """Tests for GroupService.add_member()."""

    @pytest.mark.asyncio
    async def test_adds_member_with_manage_permission(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Should add member when acting user has MANAGE permission."""
        group_id = GroupId.generate()
        acting_user_id = UserId.generate()
        new_user_id = UserId.generate()
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering",
            members=[],
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_group_repository.save = AsyncMock()

        result = await group_service.add_member(
            group_id=group_id,
            acting_user_id=acting_user_id,
            user_id=new_user_id,
            role=GroupRole.MEMBER,
        )

        assert result.has_member(new_user_id)
        mock_group_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_permission_error_without_manage(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Should raise PermissionError when user lacks MANAGE permission."""
        group_id = GroupId.generate()
        acting_user_id = UserId.generate()
        new_user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission"):
            await group_service.add_member(
                group_id=group_id,
                acting_user_id=acting_user_id,
                user_id=new_user_id,
                role=GroupRole.MEMBER,
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
        acting_user_id = UserId.generate()
        new_user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await group_service.add_member(
                group_id=group_id,
                acting_user_id=acting_user_id,
                user_id=new_user_id,
                role=GroupRole.MEMBER,
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
        acting_user_id = UserId.generate()
        new_user_id = UserId.generate()
        other_tenant = TenantId.generate()
        group = Group(
            id=group_id,
            tenant_id=other_tenant,
            name="Engineering",
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)

        with pytest.raises(ValueError, match="different tenant"):
            await group_service.add_member(
                group_id=group_id,
                acting_user_id=acting_user_id,
                user_id=new_user_id,
                role=GroupRole.MEMBER,
            )


class TestRemoveMember:
    """Tests for GroupService.remove_member()."""

    @pytest.mark.asyncio
    async def test_removes_member_with_manage_permission(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Should remove member when acting user has MANAGE permission."""
        group_id = GroupId.generate()
        acting_user_id = UserId.generate()
        member_user_id = UserId.generate()
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering",
        )
        group.add_member(acting_user_id, GroupRole.ADMIN)
        group.add_member(member_user_id, GroupRole.MEMBER)
        group.collect_events()  # Clear creation events

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_group_repository.save = AsyncMock()

        result = await group_service.remove_member(
            group_id=group_id,
            acting_user_id=acting_user_id,
            user_id=member_user_id,
        )

        assert not result.has_member(member_user_id)
        mock_group_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_permission_error_without_manage(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Should raise PermissionError when user lacks MANAGE permission."""
        group_id = GroupId.generate()
        acting_user_id = UserId.generate()
        member_user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission"):
            await group_service.remove_member(
                group_id=group_id,
                acting_user_id=acting_user_id,
                user_id=member_user_id,
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
        acting_user_id = UserId.generate()
        member_user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await group_service.remove_member(
                group_id=group_id,
                acting_user_id=acting_user_id,
                user_id=member_user_id,
            )


class TestUpdateMemberRole:
    """Tests for GroupService.update_member_role()."""

    @pytest.mark.asyncio
    async def test_updates_role_with_manage_permission(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Should update member role when acting user has MANAGE permission."""
        group_id = GroupId.generate()
        acting_user_id = UserId.generate()
        member_user_id = UserId.generate()
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering",
        )
        group.add_member(acting_user_id, GroupRole.ADMIN)
        group.add_member(member_user_id, GroupRole.MEMBER)
        group.collect_events()

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_group_repository.save = AsyncMock()

        result = await group_service.update_member_role(
            group_id=group_id,
            acting_user_id=acting_user_id,
            user_id=member_user_id,
            new_role=GroupRole.ADMIN,
        )

        assert result.get_member_role(member_user_id) == GroupRole.ADMIN
        mock_group_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_permission_error_without_manage(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Should raise PermissionError when user lacks MANAGE permission."""
        group_id = GroupId.generate()
        acting_user_id = UserId.generate()
        member_user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission"):
            await group_service.update_member_role(
                group_id=group_id,
                acting_user_id=acting_user_id,
                user_id=member_user_id,
                new_role=GroupRole.ADMIN,
            )


class TestListMembers:
    """Tests for GroupService.list_members()."""

    @pytest.mark.asyncio
    async def test_lists_members_with_view_permission(
        self,
        group_service: GroupService,
        mock_authz,
        tenant_id,
    ):
        """Should list members from SpiceDB when user has VIEW permission.

        Uses read_relationships to fetch explicit tuples, avoiding
        duplicate entries caused by permission computation.
        """
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)

        group_resource = f"group:{group_id.value}"
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=group_resource,
                    relation="admin",
                    subject="user:admin-user-1",
                ),
                RelationshipTuple(
                    resource=group_resource,
                    relation="member_relation",
                    subject="user:member-user-1",
                ),
            ]
        )

        members = await group_service.list_members(
            group_id=group_id,
            user_id=user_id,
        )

        assert len(members) == 2
        # Find members by user_id
        members_by_id = {m.user_id: m for m in members}
        assert members_by_id["admin-user-1"].role == GroupRole.ADMIN
        assert members_by_id["member-user-1"].role == GroupRole.MEMBER

    @pytest.mark.asyncio
    async def test_raises_permission_error_without_view(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Should raise PermissionError when user lacks VIEW permission."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks view permission"):
            await group_service.list_members(
                group_id=group_id,
                user_id=user_id,
            )

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_members(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Should return empty list when group has no members."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_authz.read_relationships = AsyncMock(return_value=[])

        members = await group_service.list_members(
            group_id=group_id,
            user_id=user_id,
        )

        assert members == []
