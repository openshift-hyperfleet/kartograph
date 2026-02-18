"""Unit tests for TenantService (TDD).

Following TDD: Write tests that describe the desired behavior,
then implement the TenantService to make these tests pass.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.services import TenantService
from iam.domain.aggregates import Tenant, Workspace
from iam.domain.value_objects import (
    MemberType,
    TenantId,
    TenantRole,
    UserId,
    WorkspaceId,
    WorkspaceRole,
)
from iam.ports.exceptions import UnauthorizedError
from iam.ports.repositories import (
    IAPIKeyRepository,
    IGroupRepository,
    ITenantRepository,
    IWorkspaceRepository,
)
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import RelationshipTuple


@pytest.fixture
def mock_tenant_repo():
    """Mock TenantRepository."""
    return Mock(spec=ITenantRepository)


@pytest.fixture
def mock_workspace_repo():
    """Mock WorkspaceRepository."""
    repo = Mock(spec=IWorkspaceRepository)
    # Default: no root workspace (async mock required for new methods)
    repo.get_root_workspace = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_group_repo():
    """Mock GroupRepository."""
    return Mock(spec=IGroupRepository)


@pytest.fixture
def mock_api_key_repo():
    """Mock APIKeyRepository."""
    return Mock(spec=IAPIKeyRepository)


@pytest.fixture
def mock_authz():
    """Mock AuthorizationProvider."""
    return Mock(spec=AuthorizationProvider)


@pytest.fixture
def mock_session():
    """Mock AsyncSession."""
    session = Mock(spec=AsyncSession)

    # Create async context manager mock
    ctx_manager = AsyncMock()
    ctx_manager.__aenter__ = AsyncMock(return_value=None)
    ctx_manager.__aexit__ = AsyncMock(return_value=None)

    session.begin = Mock(return_value=ctx_manager)
    return session


@pytest.fixture
def tenant_service(
    mock_tenant_repo,
    mock_workspace_repo,
    mock_group_repo,
    mock_api_key_repo,
    mock_authz,
    mock_session,
):
    """Create TenantService with mocked dependencies."""
    return TenantService(
        tenant_repository=mock_tenant_repo,
        workspace_repository=mock_workspace_repo,
        group_repository=mock_group_repo,
        api_key_repository=mock_api_key_repo,
        authz=mock_authz,
        session=mock_session,
    )


class TestAddMember:
    """Tests for TenantService.add_member()."""

    @pytest.mark.asyncio
    async def test_adds_member_to_tenant(
        self, tenant_service, mock_tenant_repo, mock_authz, mock_session
    ):
        """Test that add_member adds a user to a tenant."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        # Mock tenant retrieval
        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()

        # Mock SpiceDB: user has no current role
        mock_authz.read_relationships = AsyncMock(return_value=[])

        # Execute
        await tenant_service.add_member(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole.MEMBER,
            requesting_user_id=admin_id,
        )

        # Verify tenant was saved
        mock_tenant_repo.save.assert_called_once()
        saved_tenant = mock_tenant_repo.save.call_args[0][0]

        # Verify event was emitted
        events = saved_tenant.collect_events()
        assert len(events) == 1
        assert events[0].user_id == user_id.value
        assert events[0].role == TenantRole.MEMBER.value

    @pytest.mark.asyncio
    async def test_adds_admin_to_tenant(
        self, tenant_service, mock_tenant_repo, mock_authz, mock_session
    ):
        """Test that add_member can add an admin."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()

        # Mock SpiceDB: user has no current role
        mock_authz.read_relationships = AsyncMock(return_value=[])

        await tenant_service.add_member(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole.ADMIN,
            requesting_user_id=admin_id,
        )

        mock_tenant_repo.save.assert_called_once()
        saved_tenant = mock_tenant_repo.save.call_args[0][0]
        events = saved_tenant.collect_events()
        assert events[0].role == TenantRole.ADMIN.value

    @pytest.mark.asyncio
    async def test_replaces_role_when_user_has_different_role(
        self, tenant_service, mock_tenant_repo, mock_authz, mock_session
    ):
        """Test that adding user with different role removes old role first."""
        from iam.domain.events import TenantMemberAdded, TenantMemberRemoved

        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()

        # Mock SpiceDB: user currently has admin role
        tenant_resource = f"tenant:{tenant_id.value}"
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=tenant_resource,
                    relation="admin",
                    subject=f"user:{user_id.value}",
                ),
            ]
        )

        # Add user as member (should replace admin role)
        await tenant_service.add_member(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole.MEMBER,
            requesting_user_id=admin_id,
        )

        # Verify events: should have MemberRemoved (admin) + MemberAdded (member)
        saved_tenant = mock_tenant_repo.save.call_args[0][0]
        events = saved_tenant.collect_events()
        assert len(events) == 2
        assert isinstance(events[0], TenantMemberRemoved)
        assert events[0].role == TenantRole.ADMIN.value
        assert isinstance(events[1], TenantMemberAdded)
        assert events[1].role == TenantRole.MEMBER.value

    @pytest.mark.asyncio
    async def test_no_replacement_when_same_role(
        self, tenant_service, mock_tenant_repo, mock_authz, mock_session
    ):
        """Test that adding user with same role does not emit remove event."""
        from iam.domain.events import TenantMemberAdded

        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()

        # Mock SpiceDB: user currently has member role
        tenant_resource = f"tenant:{tenant_id.value}"
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=tenant_resource,
                    relation="member",
                    subject=f"user:{user_id.value}",
                ),
            ]
        )

        # Add user as member again (same role)
        await tenant_service.add_member(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole.MEMBER,
            requesting_user_id=admin_id,
        )

        # Only MemberAdded event, no MemberRemoved
        saved_tenant = mock_tenant_repo.save.call_args[0][0]
        events = saved_tenant.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TenantMemberAdded)

    @pytest.mark.asyncio
    async def test_raises_error_if_tenant_not_found(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that add_member raises ValueError if tenant doesn't exist."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        mock_tenant_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError) as exc_info:
            await tenant_service.add_member(
                tenant_id=tenant_id,
                user_id=user_id,
                role=TenantRole.MEMBER,
                requesting_user_id=admin_id,
            )

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_unauthorized_if_no_permission(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that add_member raises UnauthorizedError if user lacks permission."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check to deny permission
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError):
            await tenant_service.add_member(
                tenant_id=tenant_id,
                user_id=user_id,
                role=TenantRole.MEMBER,
                requesting_user_id=admin_id,
            )

        # Verify repository was never called
        mock_tenant_repo.get_by_id.assert_not_called()
        mock_tenant_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_admin_grants_root_workspace_admin(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo, mock_authz
    ):
        """Test that adding a tenant admin auto-grants root workspace admin.

        When a user is added as tenant ADMIN, they should automatically be
        granted ADMIN role on the tenant's root workspace.
        """
        from iam.domain.events import WorkspaceMemberAdded

        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        # Mock tenant retrieval
        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()

        # Mock SpiceDB: user has no current tenant role
        mock_authz.read_relationships = AsyncMock(return_value=[])

        # Mock root workspace exists
        root_workspace = Workspace.create_root(name="Root", tenant_id=tenant_id)
        root_workspace.collect_events()  # clear creation events
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=root_workspace)
        mock_workspace_repo.save = AsyncMock()

        # Execute
        await tenant_service.add_member(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole.ADMIN,
            requesting_user_id=admin_id,
        )

        # Verify workspace was saved with member added
        mock_workspace_repo.save.assert_called_once()
        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        events = saved_workspace.collect_events()

        member_added_events = [e for e in events if isinstance(e, WorkspaceMemberAdded)]
        assert len(member_added_events) == 1
        assert member_added_events[0].member_id == user_id.value
        assert member_added_events[0].role == "admin"

    @pytest.mark.asyncio
    async def test_add_member_does_not_grant_root_workspace_access(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo, mock_authz
    ):
        """Test that adding a regular MEMBER does not auto-grant workspace access.

        Only tenant ADMIN should get auto-granted root workspace admin.
        Regular members get create_child via the creator_tenant relation in SpiceDB.
        """
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()

        # Mock SpiceDB: user has no current role
        mock_authz.read_relationships = AsyncMock(return_value=[])

        await tenant_service.add_member(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole.MEMBER,
            requesting_user_id=admin_id,
        )

        # Verify workspace_repo.save was NOT called (no workspace grant)
        mock_workspace_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_downgrade_admin_to_member_revokes_root_workspace_admin(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo, mock_authz
    ):
        """Test that downgrading tenant ADMIN to MEMBER revokes root workspace admin.

        When a user's tenant role is changed from ADMIN to MEMBER, their
        root workspace admin access should be revoked.
        """
        from iam.domain.events import WorkspaceMemberRemoved

        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()

        # Mock SpiceDB: user currently has admin tenant role
        tenant_resource = f"tenant:{tenant_id.value}"
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=tenant_resource,
                    relation="admin",
                    subject=f"user:{user_id.value}",
                ),
            ]
        )

        # Mock root workspace exists with user as admin member
        root_workspace = Workspace.create_root(name="Root", tenant_id=tenant_id)
        root_workspace.collect_events()
        from iam.domain.value_objects import MemberType, WorkspaceRole

        root_workspace.add_member(
            member_id=user_id.value,
            member_type=MemberType.USER,
            role=WorkspaceRole.ADMIN,
        )
        root_workspace.collect_events()  # clear add events
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=root_workspace)
        mock_workspace_repo.save = AsyncMock()

        # Downgrade: add as MEMBER (should replace ADMIN->MEMBER)
        await tenant_service.add_member(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole.MEMBER,
            requesting_user_id=admin_id,
        )

        # Verify workspace was saved with member removed (revoke admin)
        mock_workspace_repo.save.assert_called_once()
        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        events = saved_workspace.collect_events()

        member_removed_events = [
            e for e in events if isinstance(e, WorkspaceMemberRemoved)
        ]
        assert len(member_removed_events) == 1
        assert member_removed_events[0].member_id == user_id.value
        assert member_removed_events[0].role == "admin"

    @pytest.mark.asyncio
    async def test_add_admin_handles_missing_root_workspace(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo, mock_authz
    ):
        """Test that add_member handles missing root workspace gracefully.

        Root workspace might not exist yet (e.g., during migration).
        The service should log a warning but not fail.
        """
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()

        # Mock SpiceDB: user has no current role
        mock_authz.read_relationships = AsyncMock(return_value=[])

        # Mock root workspace does NOT exist
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=None)

        # Should not raise - graceful handling
        await tenant_service.add_member(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole.ADMIN,
            requesting_user_id=admin_id,
        )

        # Tenant should still be saved
        mock_tenant_repo.save.assert_called_once()
        # Workspace should NOT be saved (no root workspace)
        mock_workspace_repo.save.assert_not_called()


class TestRemoveMember:
    """Tests for TenantService.remove_member()."""

    @pytest.mark.asyncio
    async def test_removes_member_from_tenant(
        self, tenant_service, mock_tenant_repo, mock_authz, mock_session
    ):
        """Test that remove_member removes a user from a tenant."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()
        mock_tenant_repo.is_last_admin = AsyncMock(return_value=False)

        await tenant_service.remove_member(
            tenant_id=tenant_id,
            user_id=user_id,
            requesting_user_id=admin_id,
        )

        mock_tenant_repo.save.assert_called_once()
        saved_tenant = mock_tenant_repo.save.call_args[0][0]
        events = saved_tenant.collect_events()
        assert len(events) == 1
        assert events[0].user_id == user_id.value

    @pytest.mark.asyncio
    async def test_checks_if_last_admin(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that remove_member checks if user is last admin."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.is_last_admin = AsyncMock(return_value=False)
        mock_tenant_repo.save = AsyncMock()

        await tenant_service.remove_member(
            tenant_id=tenant_id,
            user_id=user_id,
            requesting_user_id=admin_id,
        )

        # Verify is_last_admin was called
        mock_tenant_repo.is_last_admin.assert_called_once_with(
            tenant_id, user_id, mock_authz
        )

    @pytest.mark.asyncio
    async def test_raises_error_if_last_admin(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that remove_member raises error if removing last admin."""
        from iam.domain.exceptions import CannotRemoveLastAdminError

        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.is_last_admin = AsyncMock(return_value=True)

        with pytest.raises(CannotRemoveLastAdminError):
            await tenant_service.remove_member(
                tenant_id=tenant_id,
                user_id=user_id,
                requesting_user_id=admin_id,
            )

    @pytest.mark.asyncio
    async def test_raises_error_if_tenant_not_found(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that remove_member raises ValueError if tenant doesn't exist."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        mock_tenant_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError) as exc_info:
            await tenant_service.remove_member(
                tenant_id=tenant_id,
                user_id=user_id,
                requesting_user_id=admin_id,
            )

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_unauthorized_if_no_permission(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that remove_member raises UnauthorizedError if user lacks permission."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check to deny permission
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError):
            await tenant_service.remove_member(
                tenant_id=tenant_id,
                user_id=user_id,
                requesting_user_id=admin_id,
            )

        # Verify repository was never called
        mock_tenant_repo.get_by_id.assert_not_called()
        mock_tenant_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_admin_revokes_root_workspace_admin(
        self,
        tenant_service,
        mock_tenant_repo,
        mock_workspace_repo,
        mock_authz,
    ):
        """Test that removing a tenant admin revokes their root workspace admin access."""
        from iam.domain.events import WorkspaceMemberRemoved
        from iam.domain.value_objects import MemberType, WorkspaceRole

        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()
        mock_tenant_repo.is_last_admin = AsyncMock(return_value=False)

        # Mock root workspace with user as admin
        root_workspace = Workspace.create_root(name="Root", tenant_id=tenant_id)
        root_workspace.collect_events()
        root_workspace.add_member(
            member_id=user_id.value,
            member_type=MemberType.USER,
            role=WorkspaceRole.ADMIN,
        )
        root_workspace.collect_events()  # clear events
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=root_workspace)
        mock_workspace_repo.save = AsyncMock()

        await tenant_service.remove_member(
            tenant_id=tenant_id,
            user_id=user_id,
            requesting_user_id=admin_id,
        )

        # Verify workspace was saved with member removed
        mock_workspace_repo.save.assert_called_once()
        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        events = saved_workspace.collect_events()

        member_removed_events = [
            e for e in events if isinstance(e, WorkspaceMemberRemoved)
        ]
        assert len(member_removed_events) == 1
        assert member_removed_events[0].member_id == user_id.value

    @pytest.mark.asyncio
    async def test_remove_member_revokes_root_workspace_access(
        self,
        tenant_service,
        mock_tenant_repo,
        mock_workspace_repo,
        mock_authz,
    ):
        """Test that removing a regular member also revokes any root workspace access."""

        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()
        mock_tenant_repo.is_last_admin = AsyncMock(return_value=False)

        # Mock root workspace - user is NOT a member
        root_workspace = Workspace.create_root(name="Root", tenant_id=tenant_id)
        root_workspace.collect_events()
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=root_workspace)
        mock_workspace_repo.save = AsyncMock()

        await tenant_service.remove_member(
            tenant_id=tenant_id,
            user_id=user_id,
            requesting_user_id=admin_id,
        )

        # Workspace should NOT be saved since user is not a workspace member
        mock_workspace_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_member_handles_missing_root_workspace(
        self,
        tenant_service,
        mock_tenant_repo,
        mock_workspace_repo,
        mock_authz,
    ):
        """Test that remove_member handles missing root workspace gracefully."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        admin_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.save = AsyncMock()
        mock_tenant_repo.is_last_admin = AsyncMock(return_value=False)

        # Mock root workspace does NOT exist
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=None)

        # Should not raise
        await tenant_service.remove_member(
            tenant_id=tenant_id,
            user_id=user_id,
            requesting_user_id=admin_id,
        )

        # Tenant was saved
        mock_tenant_repo.save.assert_called_once()
        # Workspace was NOT saved (no root workspace)
        mock_workspace_repo.save.assert_not_called()


class TestListMembers:
    """Tests for TenantService.list_members() using read_relationships."""

    @pytest.mark.asyncio
    async def test_lists_members_from_spicedb(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_members queries SpiceDB using read_relationships."""
        tenant_id = TenantId.generate()
        requesting_user_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        # Mock tenant existence
        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)

        # Mock SpiceDB read_relationships response
        tenant_resource = f"tenant:{tenant_id.value}"
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=tenant_resource,
                    relation="admin",
                    subject="user:user-admin-1",
                ),
                RelationshipTuple(
                    resource=tenant_resource,
                    relation="admin",
                    subject="user:user-admin-2",
                ),
                RelationshipTuple(
                    resource=tenant_resource,
                    relation="member",
                    subject="user:user-member-1",
                ),
            ]
        )

        # Execute
        members = await tenant_service.list_members(
            tenant_id=tenant_id, requesting_user_id=requesting_user_id
        )

        # Verify
        assert len(members) == 3
        assert ("user-admin-1", "admin") in members
        assert ("user-admin-2", "admin") in members
        assert ("user-member-1", "member") in members

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_tenant_with_no_members(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_members returns empty list if no members."""
        tenant_id = TenantId.generate()
        requesting_user_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_authz.read_relationships = AsyncMock(return_value=[])

        members = await tenant_service.list_members(
            tenant_id=tenant_id, requesting_user_id=requesting_user_id
        )

        assert members == []

    @pytest.mark.asyncio
    async def test_returns_none_if_tenant_not_found(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_members returns None if tenant doesn't exist."""
        tenant_id = TenantId.generate()
        requesting_user_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        mock_tenant_repo.get_by_id = AsyncMock(return_value=None)

        result = await tenant_service.list_members(
            tenant_id=tenant_id, requesting_user_id=requesting_user_id
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_raises_unauthorized_if_no_permission(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_members raises UnauthorizedError if user lacks permission."""
        tenant_id = TenantId.generate()
        requesting_user_id = UserId.from_string("admin-456")

        # Mock authorization check to deny permission
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError):
            await tenant_service.list_members(
                tenant_id=tenant_id, requesting_user_id=requesting_user_id
            )

        # Verify repository was never called
        mock_tenant_repo.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_filters_non_role_relations(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_members ignores tuples with non-role relations."""
        tenant_id = TenantId.generate()
        requesting_user_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)

        tenant_resource = f"tenant:{tenant_id.value}"
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=tenant_resource,
                    relation="admin",
                    subject="user:user-1",
                ),
                RelationshipTuple(
                    resource=tenant_resource,
                    relation="root_workspace",
                    subject="workspace:ws-1",
                ),
            ]
        )

        members = await tenant_service.list_members(
            tenant_id=tenant_id, requesting_user_id=requesting_user_id
        )

        # Only the admin tuple should be included
        assert len(members) == 1
        assert ("user-1", "admin") in members

    @pytest.mark.asyncio
    async def test_uses_read_relationships_not_lookup_subjects(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_members uses read_relationships (single call)."""
        tenant_id = TenantId.generate()
        requesting_user_id = UserId.from_string("admin-456")

        mock_authz.check_permission = AsyncMock(return_value=True)

        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_authz.read_relationships = AsyncMock(return_value=[])

        await tenant_service.list_members(
            tenant_id=tenant_id, requesting_user_id=requesting_user_id
        )

        # Single call to read_relationships with subject_type filter
        mock_authz.read_relationships.assert_called_once_with(
            resource_type="tenant",
            resource_id=tenant_id.value,
            subject_type="user",
        )


class TestCreateTenant:
    """Tests for TenantService.create_tenant()."""

    @pytest.mark.asyncio
    async def test_creates_tenant(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo
    ):
        """Test that create_tenant creates a tenant."""
        mock_tenant_repo.save = AsyncMock()
        mock_workspace_repo.save = AsyncMock()
        creator_id = UserId.from_string("creator-user-1")

        tenant = await tenant_service.create_tenant(
            name="Acme Corp", creator_id=creator_id
        )

        assert tenant.name == "Acme Corp"
        mock_tenant_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_grants_creator_admin_access(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo
    ):
        """Test that create_tenant grants the creator admin access."""
        mock_tenant_repo.save = AsyncMock()
        mock_workspace_repo.save = AsyncMock()
        creator_id = UserId.from_string("creator-user-1")

        await tenant_service.create_tenant(name="Acme Corp", creator_id=creator_id)

        # Verify the saved tenant has both TenantCreated and TenantMemberAdded events
        saved_tenant = mock_tenant_repo.save.call_args[0][0]
        events = saved_tenant.collect_events()

        # Should have TenantCreated + TenantMemberAdded
        from iam.domain.events import TenantCreated, TenantMemberAdded

        event_types = [type(e) for e in events]
        assert TenantCreated in event_types
        assert TenantMemberAdded in event_types

        # Verify the member added event has the right data
        member_event = next(e for e in events if isinstance(e, TenantMemberAdded))
        assert member_event.user_id == creator_id.value
        assert member_event.role == TenantRole.ADMIN.value

    @pytest.mark.asyncio
    async def test_creates_root_workspace_on_tenant_creation(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo
    ):
        """Test that creating a tenant auto-creates a root workspace and grants creator admin."""
        mock_tenant_repo.save = AsyncMock()
        mock_workspace_repo.save = AsyncMock()
        creator_id = UserId.from_string("creator-user-1")

        tenant = await tenant_service.create_tenant(
            name="Acme Corp", creator_id=creator_id
        )

        # Verify workspace_repository.save was called once
        mock_workspace_repo.save.assert_called_once()

        # Verify the saved workspace is a root workspace
        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        assert saved_workspace.is_root is True
        assert saved_workspace.tenant_id == tenant.id
        assert saved_workspace.parent_workspace_id is None

        # Verify creator was granted admin access to root workspace
        from iam.domain.events import WorkspaceMemberAdded

        workspace_events = saved_workspace.collect_events()
        member_events = [
            e for e in workspace_events if isinstance(e, WorkspaceMemberAdded)
        ]
        assert len(member_events) == 1

        member_event = member_events[0]
        assert member_event.member_id == creator_id.value
        assert member_event.member_type == MemberType.USER.value
        assert member_event.role == WorkspaceRole.ADMIN.value

    @pytest.mark.asyncio
    async def test_root_workspace_uses_settings_default_name(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo
    ):
        """Test that root workspace uses default_workspace_name from settings."""
        mock_tenant_repo.save = AsyncMock()
        mock_workspace_repo.save = AsyncMock()
        creator_id = UserId.from_string("creator-user-1")

        # Patch settings to return a custom default workspace name
        mock_settings = Mock()
        mock_settings.default_workspace_name = "My Default Workspace"

        with patch(
            "iam.application.services.tenant_service.get_iam_settings",
            return_value=mock_settings,
        ):
            await tenant_service.create_tenant(name="Acme Corp", creator_id=creator_id)

        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        assert saved_workspace.name == "My Default Workspace"

    @pytest.mark.asyncio
    async def test_root_workspace_falls_back_to_tenant_name(
        self, tenant_service, mock_tenant_repo, mock_workspace_repo
    ):
        """Test that root workspace falls back to tenant name when no settings default."""
        mock_tenant_repo.save = AsyncMock()
        mock_workspace_repo.save = AsyncMock()
        creator_id = UserId.from_string("creator-user-1")

        # Patch settings to return None for default_workspace_name
        mock_settings = Mock()
        mock_settings.default_workspace_name = None

        with patch(
            "iam.application.services.tenant_service.get_iam_settings",
            return_value=mock_settings,
        ):
            await tenant_service.create_tenant(name="Acme Corp", creator_id=creator_id)

        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        assert saved_workspace.name == "Acme Corp"


class TestGetTenant:
    """Tests for TenantService.get_tenant() with VIEW permission check."""

    @pytest.mark.asyncio
    async def test_returns_tenant_when_user_has_view_permission(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that get_tenant returns tenant when user has VIEW permission."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        tenant = Tenant(id=tenant_id, name="Acme Corp")

        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_authz.check_permission = AsyncMock(return_value=True)

        result = await tenant_service.get_tenant(tenant_id, user_id=user_id)

        assert result is not None
        assert result.id == tenant_id
        assert result.name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_returns_none_when_tenant_not_found(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that get_tenant returns None when tenant doesn't exist."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")

        mock_tenant_repo.get_by_id = AsyncMock(return_value=None)

        result = await tenant_service.get_tenant(tenant_id, user_id=user_id)

        assert result is None
        # Should not check permission if tenant doesn't exist
        mock_authz.check_permission.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_user_lacks_view_permission(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that get_tenant returns None when user lacks VIEW permission.

        Acts as if tenant doesn't exist to avoid leaking information about
        tenants the user cannot access.
        """
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        tenant = Tenant(id=tenant_id, name="Acme Corp")

        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_authz.check_permission = AsyncMock(return_value=False)

        result = await tenant_service.get_tenant(tenant_id, user_id=user_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_checks_view_permission_via_spicedb(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that get_tenant checks VIEW permission with correct SpiceDB args."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("user-123")
        tenant = Tenant(id=tenant_id, name="Acme Corp")

        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_authz.check_permission = AsyncMock(return_value=True)

        await tenant_service.get_tenant(tenant_id, user_id=user_id)

        mock_authz.check_permission.assert_called_once_with(
            resource=f"tenant:{tenant_id.value}",
            permission="view",
            subject=f"user:{user_id.value}",
        )


class TestListTenants:
    """Tests for TenantService.list_tenants() with VIEW permission filtering."""

    @pytest.mark.asyncio
    async def test_returns_only_tenants_user_can_view(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_tenants filters to tenants user has VIEW permission on."""
        user_id = UserId.from_string("user-123")

        tenant_a = Tenant(id=TenantId.generate(), name="Acme Corp")
        tenant_b = Tenant(id=TenantId.generate(), name="Wayne Enterprises")
        tenant_c = Tenant(id=TenantId.generate(), name="Stark Industries")

        mock_tenant_repo.list_all = AsyncMock(
            return_value=[tenant_a, tenant_b, tenant_c]
        )

        # User can only view tenant_a and tenant_c
        mock_authz.lookup_resources = AsyncMock(
            return_value=[tenant_a.id.value, tenant_c.id.value]
        )

        result = await tenant_service.list_tenants(user_id=user_id)

        assert len(result) == 2
        result_ids = {t.id.value for t in result}
        assert tenant_a.id.value in result_ids
        assert tenant_c.id.value in result_ids
        assert tenant_b.id.value not in result_ids

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_user_has_no_access(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_tenants returns empty list when user has no VIEW permission."""
        user_id = UserId.from_string("user-123")

        tenant_a = Tenant(id=TenantId.generate(), name="Acme Corp")
        mock_tenant_repo.list_all = AsyncMock(return_value=[tenant_a])

        # User has no access to any tenants
        mock_authz.lookup_resources = AsyncMock(return_value=[])

        result = await tenant_service.list_tenants(user_id=user_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_calls_lookup_resources_with_correct_args(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_tenants calls lookup_resources with correct SpiceDB args."""
        user_id = UserId.from_string("user-123")

        mock_tenant_repo.list_all = AsyncMock(return_value=[])
        mock_authz.lookup_resources = AsyncMock(return_value=[])

        await tenant_service.list_tenants(user_id=user_id)

        mock_authz.lookup_resources.assert_called_once_with(
            resource_type="tenant",
            permission="view",
            subject=f"user:{user_id.value}",
        )

    @pytest.mark.asyncio
    async def test_returns_all_accessible_tenants(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_tenants returns all tenants when user has VIEW on all."""
        user_id = UserId.from_string("user-123")

        tenant_a = Tenant(id=TenantId.generate(), name="Acme Corp")
        tenant_b = Tenant(id=TenantId.generate(), name="Wayne Enterprises")

        mock_tenant_repo.list_all = AsyncMock(return_value=[tenant_a, tenant_b])

        # User can view both tenants
        mock_authz.lookup_resources = AsyncMock(
            return_value=[tenant_a.id.value, tenant_b.id.value]
        )

        result = await tenant_service.list_tenants(user_id=user_id)

        assert len(result) == 2


class TestDeleteTenant:
    """Tests for TenantService.delete_tenant()."""

    @pytest.mark.asyncio
    async def test_deletes_tenant(
        self,
        tenant_service,
        mock_tenant_repo,
        mock_workspace_repo,
        mock_group_repo,
        mock_api_key_repo,
        mock_authz,
    ):
        """Test that delete_tenant deletes a tenant."""
        tenant_id = TenantId.generate()
        admin_id = UserId.from_string("admin-456")
        tenant = Tenant(id=tenant_id, name="Acme Corp")

        # Mock authorization check - user has administrate permission
        mock_authz.check_permission = AsyncMock(return_value=True)

        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.delete = AsyncMock(return_value=True)
        mock_workspace_repo.list_by_tenant = AsyncMock(return_value=[])
        mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
        mock_api_key_repo.list = AsyncMock(return_value=[])
        mock_authz.read_relationships = AsyncMock(return_value=[])

        result = await tenant_service.delete_tenant(
            tenant_id, requesting_user_id=admin_id
        )

        assert result is True
        mock_tenant_repo.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_deletes_workspaces_on_tenant_deletion(
        self,
        tenant_service,
        mock_tenant_repo,
        mock_workspace_repo,
        mock_group_repo,
        mock_api_key_repo,
        mock_authz,
    ):
        """Test that deleting tenant cascades to workspaces."""
        from datetime import UTC, datetime

        tenant_id = TenantId.generate()
        admin_id = UserId.from_string("admin-456")
        tenant = Tenant(id=tenant_id, name="Acme Corp")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        # Create test workspace
        workspace = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=tenant_id,
            name="Root",
            parent_workspace_id=None,
            is_root=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.delete = AsyncMock(return_value=True)
        mock_workspace_repo.list_by_tenant = AsyncMock(return_value=[workspace])
        mock_workspace_repo.delete = AsyncMock(return_value=True)
        mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
        mock_api_key_repo.list = AsyncMock(return_value=[])
        mock_authz.read_relationships = AsyncMock(return_value=[])

        await tenant_service.delete_tenant(tenant_id, requesting_user_id=admin_id)

        # Verify workspace was deleted
        mock_workspace_repo.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_tenant_returns_false_if_not_found(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that delete_tenant returns False if tenant doesn't exist."""
        tenant_id = TenantId.generate()
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        mock_tenant_repo.get_by_id = AsyncMock(return_value=None)

        result = await tenant_service.delete_tenant(
            tenant_id, requesting_user_id=admin_id
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_tenant_deletes_multiple_workspaces(
        self,
        tenant_service,
        mock_tenant_repo,
        mock_workspace_repo,
        mock_group_repo,
        mock_api_key_repo,
        mock_authz,
    ):
        """Test that delete_tenant deletes all workspaces belonging to tenant."""
        from datetime import UTC, datetime

        tenant_id = TenantId.generate()
        admin_id = UserId.from_string("admin-456")
        tenant = Tenant(id=tenant_id, name="Acme Corp")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        # Create multiple test workspaces
        root_ws = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=tenant_id,
            name="Root",
            parent_workspace_id=None,
            is_root=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        child_ws = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=tenant_id,
            name="Child",
            parent_workspace_id=root_ws.id,
            is_root=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)
        mock_tenant_repo.delete = AsyncMock(return_value=True)
        mock_workspace_repo.list_by_tenant = AsyncMock(return_value=[root_ws, child_ws])
        mock_workspace_repo.delete = AsyncMock(return_value=True)
        mock_group_repo.list_by_tenant = AsyncMock(return_value=[])
        mock_api_key_repo.list = AsyncMock(return_value=[])
        mock_authz.read_relationships = AsyncMock(return_value=[])

        await tenant_service.delete_tenant(tenant_id, requesting_user_id=admin_id)

        # Verify workspace_repository.delete was called for each workspace
        assert mock_workspace_repo.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_tenant_raises_unauthorized_if_no_permission(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that delete_tenant raises UnauthorizedError if user lacks permission."""
        tenant_id = TenantId.generate()
        user_id = UserId.from_string("unprivileged-user")

        # Mock authorization check to deny permission
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError):
            await tenant_service.delete_tenant(tenant_id, requesting_user_id=user_id)

        # Verify repository was never called
        mock_tenant_repo.get_by_id.assert_not_called()
        mock_tenant_repo.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_tenant_checks_administrate_permission(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that delete_tenant checks ADMINISTRATE permission via SpiceDB."""
        tenant_id = TenantId.generate()
        admin_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_tenant_repo.get_by_id = AsyncMock(return_value=None)

        await tenant_service.delete_tenant(tenant_id, requesting_user_id=admin_id)

        # Verify check_permission was called with ADMINISTRATE
        mock_authz.check_permission.assert_called_once()
        call_kwargs = mock_authz.check_permission.call_args
        assert "administrate" in str(call_kwargs).lower()
