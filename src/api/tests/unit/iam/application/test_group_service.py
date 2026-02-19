"""Unit tests for GroupService.

Following TDD - write tests first to define desired behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, create_autospec

from iam.application.services.group_service import GroupService
from iam.domain.aggregates import Group, User
from iam.domain.value_objects import GroupId, GroupRole, TenantId, UserId
from iam.ports.exceptions import DuplicateGroupNameError, UnauthorizedError
from iam.ports.repositories import IGroupRepository
from shared_kernel.authorization.types import (
    RelationshipTuple,
    ResourceType,
    format_resource,
    format_subject,
)


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
    from iam.application.observability.group_service_probe import GroupServiceProbe

    return create_autospec(GroupServiceProbe, instance=True)


@pytest.fixture
def mock_authz():
    """Create mock authorization provider."""
    from shared_kernel.authorization.protocols import AuthorizationProvider

    return create_autospec(AuthorizationProvider, instance=True)


@pytest.fixture
def tenant_id() -> TenantId:
    return TenantId(value="default")


@pytest.fixture
def group_service(
    mock_session, mock_group_repository, mock_authz, mock_probe, tenant_id
):
    """Create GroupService with mock dependencies."""
    from iam.application.services.group_service import GroupService

    return GroupService(
        session=mock_session,
        group_repository=mock_group_repository,
        authz=mock_authz,
        probe=mock_probe,
        scope_to_tenant=tenant_id,
    )


class TestGroupServiceInit:
    """Tests for GroupService initialization."""

    def test_stores_session(
        self, mock_session, mock_group_repository, mock_authz, group_service
    ):
        """Service should store session reference."""

        service = group_service
        assert service._session is mock_session

    def test_stores_repository(
        self, mock_session, mock_group_repository, mock_authz, group_service
    ):
        """Service should store repository reference."""

        service = group_service
        assert service._group_repository is mock_group_repository

    def test_uses_default_probe_when_not_provided(
        self, mock_session, mock_group_repository, mock_authz, group_service
    ):
        """Service should create default probe when not provided."""

        service = group_service
        assert service._probe is not None


class TestCreateGroup:
    """Tests for create_group method."""

    @pytest.mark.asyncio
    async def test_creates_group_with_creator_as_admin(
        self, group_service: GroupService, mock_group_repository
    ):
        """Should create group with creator as admin member."""
        creator_id = UserId.generate()

        mock_group_repository.save = AsyncMock()

        result = await group_service.create_group(
            name="Engineering",
            creator_id=creator_id,
        )

        # Verify group was created
        assert isinstance(result, Group)
        assert result.name == "Engineering"
        assert len(result.members) == 1
        assert result.members[0].user_id == creator_id
        assert result.members[0].role == GroupRole.ADMIN

    @pytest.mark.asyncio
    async def test_saves_group_to_repository(
        self,
        group_service: GroupService,
        mock_user_service,
        mock_group_repository,
        tenant_id,
    ):
        """Should save group via repository."""
        creator_id = UserId.generate()
        creator = User(id=creator_id, username="alice")

        mock_user_service.ensure_user = AsyncMock(return_value=creator)
        mock_group_repository.save = AsyncMock()

        await group_service.create_group(
            name="Engineering",
            creator_id=creator_id,
        )

        # Verify save was called - Group now contains tenant_id
        mock_group_repository.save.assert_called_once()
        saved_group = mock_group_repository.save.call_args[0][0]
        assert saved_group.name == "Engineering"
        assert saved_group.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_records_success_probe_event(
        self, group_service: GroupService, mock_user_service, mock_probe, tenant_id
    ):
        """Should record group_created probe event on success."""
        creator_id = UserId.generate()
        creator = User(id=creator_id, username="alice")

        mock_user_service.ensure_user = AsyncMock(return_value=creator)

        result = await group_service.create_group(
            name="Engineering",
            creator_id=creator_id,
        )

        mock_probe.group_created.assert_called_once()
        call_args = mock_probe.group_created.call_args[1]
        assert call_args["group_id"] == result.id.value
        assert call_args["name"] == "Engineering"
        assert call_args["tenant_id"] == tenant_id.value
        assert call_args["creator_id"] == creator_id.value

    @pytest.mark.asyncio
    async def test_records_failure_probe_event(
        self,
        group_service: GroupService,
        tenant_id,
        mock_user_service,
        mock_group_repository,
        mock_probe,
    ):
        """Should record group_creation_failed probe event on error."""
        creator_id = UserId.generate()
        creator = User(id=creator_id, username="alice")

        mock_user_service.ensure_user = AsyncMock(return_value=creator)
        mock_group_repository.save = AsyncMock(
            side_effect=DuplicateGroupNameError("Name exists")
        )

        with pytest.raises(DuplicateGroupNameError):
            await group_service.create_group(
                name="Engineering",
                creator_id=creator_id,
            )

        mock_probe.group_creation_failed.assert_called_once()
        call_args = mock_probe.group_creation_failed.call_args[1]
        assert call_args["name"] == "Engineering"
        assert call_args["tenant_id"] == tenant_id.value
        assert "Name exists" in call_args["error"]


class TestGetGroup:
    """Tests for get_group method."""

    @pytest.mark.asyncio
    async def test_returns_group_when_found_and_user_has_view_permission(
        self, group_service: GroupService, mock_group_repository, mock_authz, tenant_id
    ):
        """Should return group when found, tenant matches, and user has VIEW permission."""
        group_id = GroupId.generate()
        user_id = UserId.generate()
        # Group has the same tenant_id
        group = Group(id=group_id, tenant_id=tenant_id, name="Engineering")

        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_authz.check_permission = AsyncMock(return_value=True)

        result = await group_service.get_group(group_id, user_id=user_id)

        assert result == group
        mock_group_repository.get_by_id.assert_called_once_with(group_id)
        mock_authz.check_permission.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_group_not_found(
        self, group_service: GroupService, mock_group_repository, mock_authz, tenant_id
    ):
        """Should return None when group doesn't exist in repository."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_group_repository.get_by_id = AsyncMock(return_value=None)

        result = await group_service.get_group(group_id, user_id=user_id)

        assert result is None
        mock_group_repository.get_by_id.assert_called_once_with(group_id)
        mock_authz.check_permission.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_tenant_mismatch(
        self, group_service: GroupService, mock_group_repository, mock_authz, tenant_id
    ):
        """Should return None when group exists but tenant_id doesn't match."""
        group_id = GroupId.generate()
        user_id = UserId.generate()
        other_tenant_id = TenantId.generate()
        # Group has a different tenant_id
        group = Group(id=group_id, tenant_id=other_tenant_id, name="Engineering")

        mock_group_repository.get_by_id = AsyncMock(return_value=group)

        result = await group_service.get_group(group_id, user_id=user_id)

        # Returns None for security (don't leak group existence)
        assert result is None
        # Should not even check SpiceDB permission if tenant doesn't match
        mock_authz.check_permission.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_user_lacks_view_permission(
        self, group_service: GroupService, mock_group_repository, mock_authz, tenant_id
    ):
        """Should return None when user lacks VIEW permission on the group."""
        group_id = GroupId.generate()
        user_id = UserId.generate()
        group = Group(id=group_id, tenant_id=tenant_id, name="Engineering")

        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_authz.check_permission = AsyncMock(return_value=False)

        result = await group_service.get_group(group_id, user_id=user_id)

        # User lacks VIEW permission - act as if not found
        assert result is None
        mock_authz.check_permission.assert_called_once()


class TestDeleteGroup:
    """Tests for delete_group method."""

    @pytest.mark.asyncio
    async def test_deletes_group_when_authorized(
        self, group_service: GroupService, mock_group_repository, mock_authz, tenant_id
    ):
        """Should delete group when user has manage permission."""
        group_id = GroupId.generate()
        user_id = UserId.generate()
        group = Group(id=group_id, tenant_id=tenant_id, name="Engineering")

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)
        mock_group_repository.delete = AsyncMock(return_value=True)

        result = await group_service.delete_group(group_id, user_id)

        assert result is True
        mock_authz.check_permission.assert_called_once()
        # delete now takes the full aggregate
        mock_group_repository.delete.assert_called_once()
        deleted_group = mock_group_repository.delete.call_args[0][0]
        assert deleted_group.id == group_id

    @pytest.mark.asyncio
    async def test_raises_permission_error_when_unauthorized(
        self, group_service: GroupService, mock_group_repository, mock_authz
    ):
        """Should raise UnauthorizedError when user lacks manage permission."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError) as exc_info:
            await group_service.delete_group(group_id, user_id)

        assert "lacks manage permission" in str(exc_info.value)
        mock_authz.check_permission.assert_called_once()
        # Should not attempt deletion if unauthorized
        mock_group_repository.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_group_not_found(
        self, group_service: GroupService, mock_group_repository, mock_authz
    ):
        """Should return False when group doesn't exist."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=None)

        result = await group_service.delete_group(group_id, user_id)

        assert result is False
        mock_group_repository.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_tenant_mismatch(
        self, group_service: GroupService, mock_group_repository, mock_authz
    ):
        """Should return False when group exists but tenant doesn't match."""
        group_id = GroupId.generate()
        other_tenant_id = TenantId.generate()
        user_id = UserId.generate()
        # Group belongs to a different tenant
        group = Group(id=group_id, tenant_id=other_tenant_id, name="Engineering")

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_group_repository.get_by_id = AsyncMock(return_value=group)

        result = await group_service.delete_group(group_id, user_id)

        assert result is False
        mock_group_repository.delete.assert_not_called()


class TestListMembers:
    """Tests for list_members method using read_relationships."""

    @pytest.mark.asyncio
    async def test_list_members_checks_view_permission(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Test that list_members checks VIEW permission before returning members."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_authz.read_relationships = AsyncMock(return_value=[])

        result = await group_service.list_members(
            group_id=group_id,
            user_id=user_id,
        )

        assert result == []

        # Verify VIEW permission was checked
        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.GROUP, group_id.value),
            permission="view",
            subject=format_subject(ResourceType.USER, user_id.value),
        )

    @pytest.mark.asyncio
    async def test_list_members_raises_when_user_lacks_view_permission(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Test that list_members raises UnauthorizedError without VIEW permission."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError, match="lacks view permission"):
            await group_service.list_members(
                group_id=group_id,
                user_id=user_id,
            )

    @pytest.mark.asyncio
    async def test_list_members_returns_admin_and_member_roles(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Test that list_members returns members across admin and member roles."""
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)

        group_resource = f"group:{group_id.value}"

        # Simulate SpiceDB ReadRelationships returning explicit tuples
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=group_resource,
                    relation="admin",
                    subject="user:user-admin-1",
                ),
                RelationshipTuple(
                    resource=group_resource,
                    relation="member_relation",
                    subject="user:user-member-1",
                ),
            ]
        )

        result = await group_service.list_members(
            group_id=group_id,
            user_id=user_id,
        )

        assert len(result) == 2

        # Check admin
        admin_grants = [g for g in result if g.role == GroupRole.ADMIN]
        assert len(admin_grants) == 1
        assert admin_grants[0].user_id == "user-admin-1"

        # Check member
        member_grants = [g for g in result if g.role == GroupRole.MEMBER]
        assert len(member_grants) == 1
        assert member_grants[0].user_id == "user-member-1"

    @pytest.mark.asyncio
    async def test_list_members_filters_non_role_relations(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Test that list_members ignores tuples with non-role relations.

        ReadRelationships may return tuples for relations like 'tenant'
        that are not group membership roles. These should be filtered out.
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
                    subject="user:user-1",
                ),
                RelationshipTuple(
                    resource=group_resource,
                    relation="tenant",
                    subject="tenant:tenant-1",
                ),
            ]
        )

        result = await group_service.list_members(
            group_id=group_id,
            user_id=user_id,
        )

        # Only the admin tuple should be included
        assert len(result) == 1
        assert result[0].user_id == "user-1"
        assert result[0].role == GroupRole.ADMIN

    @pytest.mark.asyncio
    async def test_list_members_no_duplicate_for_admin(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Test that admins appear only once (not duplicated via permission computation).

        This is the core bug fix: previously, lookup_subjects on the 'member'
        permission would also return admins because 'member = admin + member_relation'.
        Using read_relationships returns only explicit tuples.
        """
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)

        group_resource = f"group:{group_id.value}"

        # With read_relationships, alice only appears as admin (explicit tuple)
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=group_resource,
                    relation="admin",
                    subject="user:alice",
                ),
                RelationshipTuple(
                    resource=group_resource,
                    relation="member_relation",
                    subject="user:bob",
                ),
            ]
        )

        result = await group_service.list_members(
            group_id=group_id,
            user_id=user_id,
        )

        # Alice should appear once as admin, Bob once as member
        assert len(result) == 2
        user_roles = {g.user_id: g.role for g in result}
        assert user_roles["alice"] == GroupRole.ADMIN
        assert user_roles["bob"] == GroupRole.MEMBER

    @pytest.mark.asyncio
    async def test_list_members_calls_read_relationships_once(
        self,
        group_service: GroupService,
        mock_authz,
    ):
        """Test that list_members makes a single read_relationships call.

        Performance improvement: 1 API call instead of 2 lookup_subjects calls.
        """
        group_id = GroupId.generate()
        user_id = UserId.generate()

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_authz.read_relationships = AsyncMock(return_value=[])

        await group_service.list_members(
            group_id=group_id,
            user_id=user_id,
        )

        # Single call to read_relationships
        mock_authz.read_relationships.assert_called_once_with(
            resource_type=ResourceType.GROUP.value,
            resource_id=group_id.value,
        )
