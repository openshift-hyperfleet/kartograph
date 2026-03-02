"""Unit tests for WorkspaceService authorization enforcement.

Tests permission checks on workspace operations via SpiceDB.
Following TDD - tests written first to define desired authorization behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, create_autospec

from iam.application.services.workspace_service import WorkspaceService
from iam.application.value_objects import WorkspaceAccessGrant
from iam.domain.aggregates import Workspace
from iam.domain.value_objects import (
    MemberType,
    TenantId,
    UserId,
    WorkspaceId,
    WorkspaceRole,
)
from iam.ports.exceptions import UnauthorizedError
from iam.ports.repositories import (
    IGroupRepository,
    IUserRepository,
    IWorkspaceRepository,
)
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    RelationshipTuple,
    ResourceType,
    format_resource,
    format_subject,
)


# --- Fixtures ---


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
def mock_workspace_repository():
    """Create mock workspace repository."""
    return create_autospec(IWorkspaceRepository, instance=True)


@pytest.fixture
def mock_authz():
    """Create mock authorization provider."""
    return create_autospec(AuthorizationProvider, instance=True)


@pytest.fixture
def mock_probe():
    """Create mock workspace service probe."""
    from iam.application.observability.workspace_service_probe import (
        WorkspaceServiceProbe,
    )

    return create_autospec(WorkspaceServiceProbe, instance=True)


@pytest.fixture
def mock_user_repository():
    """Create mock user repository that returns None by default (user not found)."""
    repo = create_autospec(IUserRepository, instance=True)
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_group_repository():
    """Create mock group repository that returns None by default (group not found)."""
    repo = create_autospec(IGroupRepository, instance=True)
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def tenant_id() -> TenantId:
    return TenantId.generate()


@pytest.fixture
def user_id() -> UserId:
    return UserId.generate()


@pytest.fixture
def creator_id() -> UserId:
    return UserId.generate()


@pytest.fixture
def root_workspace(tenant_id: TenantId) -> Workspace:
    """Create a root workspace for the tenant."""
    return Workspace.create_root(name="Root", tenant_id=tenant_id)


@pytest.fixture
def child_workspace(tenant_id: TenantId, root_workspace: Workspace) -> Workspace:
    """Create a child workspace in the tenant."""
    return Workspace.create(
        name="Engineering",
        tenant_id=tenant_id,
        parent_workspace_id=root_workspace.id,
    )


@pytest.fixture
def workspace_service(
    mock_session,
    mock_workspace_repository,
    mock_authz,
    mock_probe,
    mock_user_repository,
    mock_group_repository,
    tenant_id,
):
    """Create WorkspaceService with mock dependencies."""
    return WorkspaceService(
        session=mock_session,
        workspace_repository=mock_workspace_repository,
        authz=mock_authz,
        scope_to_tenant=tenant_id,
        probe=mock_probe,
        user_repository=mock_user_repository,
        group_repository=mock_group_repository,
    )


# --- VIEW Permission Tests ---


class TestWorkspaceViewPermission:
    """Tests for VIEW permission enforcement on workspace read operations."""

    @pytest.mark.asyncio
    async def test_get_workspace_checks_view_permission(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that get_workspace checks VIEW permission via SpiceDB."""
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_authz.check_permission = AsyncMock(return_value=True)

        result = await workspace_service.get_workspace(
            workspace_id=child_workspace.id,
            user_id=user_id,
        )

        assert result is not None
        assert result.id == child_workspace.id

        # Verify check_permission was called with correct args
        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.WORKSPACE, child_workspace.id.value),
            permission=Permission.VIEW.value,
            subject=format_subject(ResourceType.USER, user_id.value),
        )

    @pytest.mark.asyncio
    async def test_get_workspace_returns_none_without_view_permission(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that get_workspace returns None when user lacks VIEW permission."""
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_authz.check_permission = AsyncMock(return_value=False)

        result = await workspace_service.get_workspace(
            workspace_id=child_workspace.id,
            user_id=user_id,
        )

        assert result is None

        # Verify access denied probe was emitted
        mock_probe.workspace_access_denied.assert_called_once_with(
            workspace_id=child_workspace.id.value,
            user_id=user_id.value,
            permission="view",
        )

    @pytest.mark.asyncio
    async def test_list_workspaces_filters_by_view_permission(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        root_workspace,
    ):
        """Test that list_workspaces only returns workspaces user has VIEW permission on."""
        # Create multiple workspaces
        child1 = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=root_workspace.id,
        )
        child2 = Workspace.create(
            name="Marketing",
            tenant_id=tenant_id,
            parent_workspace_id=root_workspace.id,
        )
        all_workspaces = [root_workspace, child1, child2]
        mock_workspace_repository.list_by_tenant = AsyncMock(
            return_value=all_workspaces
        )

        # User only has VIEW on root and child1 (not child2)
        mock_authz.lookup_resources = AsyncMock(
            return_value=[root_workspace.id.value, child1.id.value]
        )

        result = await workspace_service.list_workspaces(user_id=user_id)

        assert len(result) == 2
        result_ids = {w.id for w in result}
        assert root_workspace.id in result_ids
        assert child1.id in result_ids
        assert child2.id not in result_ids

        # Verify lookup_resources was called correctly
        mock_authz.lookup_resources.assert_called_once_with(
            resource_type=ResourceType.WORKSPACE,
            permission=Permission.VIEW,
            subject=format_subject(ResourceType.USER, user_id.value),
        )

    @pytest.mark.asyncio
    async def test_list_workspaces_returns_empty_without_permissions(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        root_workspace,
    ):
        """Test that list_workspaces returns empty list when user has no VIEW permissions."""
        child1 = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=root_workspace.id,
        )
        mock_workspace_repository.list_by_tenant = AsyncMock(
            return_value=[root_workspace, child1]
        )
        # No accessible resources
        mock_authz.lookup_resources = AsyncMock(return_value=[])

        result = await workspace_service.list_workspaces(user_id=user_id)

        assert result == []

        mock_probe.workspaces_listed.assert_called_once_with(
            tenant_id=tenant_id.value,
            count=0,
            user_id=user_id.value,
        )

    @pytest.mark.asyncio
    async def test_list_members_checks_view_permission(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        mock_probe,
        user_id,
        child_workspace,
    ):
        """Test that list_members checks VIEW permission before returning members."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        # Return empty for read_relationships
        mock_authz.read_relationships = AsyncMock(return_value=[])

        result = await workspace_service.list_members(
            workspace_id=child_workspace.id,
            user_id=user_id,
        )

        assert result == []

        # Verify VIEW permission was checked
        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.WORKSPACE, child_workspace.id.value),
            permission=Permission.VIEW.value,
            subject=format_subject(ResourceType.USER, user_id.value),
        )

    @pytest.mark.asyncio
    async def test_list_members_raises_without_view_permission(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that list_members raises UnauthorizedError without VIEW permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError, match="lacks view permission"):
            await workspace_service.list_members(
                workspace_id=child_workspace.id,
                user_id=user_id,
            )


# --- MANAGE Permission Tests ---


class TestWorkspaceManagePermission:
    """Tests for MANAGE permission enforcement on workspace write operations."""

    @pytest.mark.asyncio
    async def test_delete_workspace_checks_manage_permission(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that delete_workspace checks MANAGE permission before deletion."""
        child_workspace.collect_events()  # Clear creation events
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.delete = AsyncMock(return_value=True)

        result = await workspace_service.delete_workspace(
            workspace_id=child_workspace.id,
            user_id=user_id,
        )

        assert result is True

        # Verify MANAGE permission was checked
        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.WORKSPACE, child_workspace.id.value),
            permission=Permission.MANAGE.value,
            subject=format_subject(ResourceType.USER, user_id.value),
        )

    @pytest.mark.asyncio
    async def test_delete_workspace_raises_permission_error(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that delete_workspace raises UnauthorizedError without MANAGE permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError, match="lacks manage permission"):
            await workspace_service.delete_workspace(
                workspace_id=child_workspace.id,
                user_id=user_id,
            )

    @pytest.mark.asyncio
    async def test_create_workspace_checks_manage_on_parent(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        creator_id,
        root_workspace,
    ):
        """Test that create_workspace checks CREATE_CHILD permission on parent workspace."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_name = AsyncMock(return_value=None)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=root_workspace)
        mock_workspace_repository.save = AsyncMock()

        result = await workspace_service.create_workspace(
            name="Engineering",
            parent_workspace_id=root_workspace.id,
            creator_id=creator_id,
        )

        assert result is not None
        assert result.name == "Engineering"

        # Verify CREATE_CHILD permission was checked on parent workspace
        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.WORKSPACE, root_workspace.id.value),
            permission=Permission.CREATE_CHILD.value,
            subject=format_subject(ResourceType.USER, creator_id.value),
        )

    @pytest.mark.asyncio
    async def test_create_workspace_raises_permission_error(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        creator_id,
        root_workspace,
    ):
        """Test that create_workspace raises UnauthorizedError without CREATE_CHILD on parent."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(
            UnauthorizedError, match="lacks create_child permission on parent"
        ):
            await workspace_service.create_workspace(
                name="Engineering",
                parent_workspace_id=root_workspace.id,
                creator_id=creator_id,
            )

    @pytest.mark.asyncio
    async def test_add_member_checks_manage_permission(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        mock_user_repository,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that add_member checks MANAGE permission before adding."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()
        # User exists
        mock_user_repository.get_by_id = AsyncMock(return_value=MagicMock())

        new_member_id = UserId.generate().value

        result = await workspace_service.add_member(
            workspace_id=child_workspace.id,
            acting_user_id=user_id,
            member_id=new_member_id,
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
        )

        assert result is not None

        # Verify MANAGE permission was checked
        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.WORKSPACE, child_workspace.id.value),
            permission=Permission.MANAGE.value,
            subject=format_subject(ResourceType.USER, user_id.value),
        )

    @pytest.mark.asyncio
    async def test_add_member_raises_permission_error(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that add_member raises UnauthorizedError without MANAGE permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError, match="lacks manage permission"):
            await workspace_service.add_member(
                workspace_id=child_workspace.id,
                acting_user_id=user_id,
                member_id="some-user-id",
                member_type=MemberType.USER,
                role=WorkspaceRole.MEMBER,
            )

    @pytest.mark.asyncio
    async def test_remove_member_checks_manage_permission(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that remove_member checks MANAGE permission before removing."""
        # Add a member first
        member_id = UserId.generate().value
        child_workspace.add_member(member_id, MemberType.USER, WorkspaceRole.MEMBER)

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

        result = await workspace_service.remove_member(
            workspace_id=child_workspace.id,
            acting_user_id=user_id,
            member_id=member_id,
            member_type=MemberType.USER,
        )

        assert result is not None

        # Verify MANAGE permission was checked
        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.WORKSPACE, child_workspace.id.value),
            permission=Permission.MANAGE.value,
            subject=format_subject(ResourceType.USER, user_id.value),
        )

    @pytest.mark.asyncio
    async def test_remove_member_raises_permission_error(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that remove_member raises UnauthorizedError without MANAGE permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError, match="lacks manage permission"):
            await workspace_service.remove_member(
                workspace_id=child_workspace.id,
                acting_user_id=user_id,
                member_id="some-user-id",
                member_type=MemberType.USER,
            )


# --- Last-Admin Protection (Service-level) ---


class TestWorkspaceLastAdminProtection:
    """Tests for last-admin protection at the service layer."""

    @pytest.mark.asyncio
    async def test_remove_last_admin_raises_error(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that removing the last admin from a workspace raises CannotRemoveLastAdminError."""
        from iam.domain.exceptions import CannotRemoveLastAdminError

        admin_id = UserId.generate().value
        child_workspace.add_member(admin_id, MemberType.USER, WorkspaceRole.ADMIN)

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

        with pytest.raises(CannotRemoveLastAdminError):
            await workspace_service.remove_member(
                workspace_id=child_workspace.id,
                acting_user_id=user_id,
                member_id=admin_id,
                member_type=MemberType.USER,
            )

        # Save should not have been called
        mock_workspace_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_last_admin_role_raises_error(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that changing the last admin's role raises CannotRemoveLastAdminError."""
        from iam.domain.exceptions import CannotRemoveLastAdminError

        admin_id = UserId.generate().value
        child_workspace.add_member(admin_id, MemberType.USER, WorkspaceRole.ADMIN)

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

        with pytest.raises(CannotRemoveLastAdminError):
            await workspace_service.update_member_role(
                workspace_id=child_workspace.id,
                acting_user_id=user_id,
                member_id=admin_id,
                member_type=MemberType.USER,
                new_role=WorkspaceRole.MEMBER,
            )

        mock_workspace_repository.save.assert_not_called()


# --- Member Management Tests ---


class TestWorkspaceMemberManagement:
    """Tests for member management operations (add, remove, list)."""

    @pytest.mark.asyncio
    async def test_add_member_adds_user_to_workspace(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        mock_user_repository,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that add_member successfully adds a user member to workspace."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()
        # User exists
        mock_user_repository.get_by_id = AsyncMock(return_value=MagicMock())

        new_member_id = UserId.generate().value

        result = await workspace_service.add_member(
            workspace_id=child_workspace.id,
            acting_user_id=user_id,
            member_id=new_member_id,
            member_type=MemberType.USER,
            role=WorkspaceRole.EDITOR,
        )

        # Assert member was added to workspace
        assert result.has_member(new_member_id, MemberType.USER)
        assert (
            result.get_member_role(new_member_id, MemberType.USER)
            == WorkspaceRole.EDITOR
        )

        # Assert repository save was called
        mock_workspace_repository.save.assert_called_once()

        # Assert probe was called
        mock_probe.workspace_member_added.assert_called_once_with(
            workspace_id=child_workspace.id.value,
            member_id=new_member_id,
            member_type=MemberType.USER.value,
            role=WorkspaceRole.EDITOR.value,
            acting_user_id=user_id.value,
        )

    @pytest.mark.asyncio
    async def test_add_member_adds_group_to_workspace(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        mock_group_repository,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that add_member successfully adds a group member to workspace."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()
        # Group exists
        mock_group_repository.get_by_id = AsyncMock(return_value=MagicMock())

        from iam.domain.value_objects import GroupId

        group_id = GroupId.generate()

        result = await workspace_service.add_member(
            workspace_id=child_workspace.id,
            acting_user_id=user_id,
            member_id=group_id.value,
            member_type=MemberType.GROUP,
            role=WorkspaceRole.ADMIN,
        )

        assert result.has_member(group_id.value, MemberType.GROUP)
        assert (
            result.get_member_role(group_id.value, MemberType.GROUP)
            == WorkspaceRole.ADMIN
        )

        mock_probe.workspace_member_added.assert_called_once_with(
            workspace_id=child_workspace.id.value,
            member_id=group_id.value,
            member_type=MemberType.GROUP.value,
            role=WorkspaceRole.ADMIN.value,
            acting_user_id=user_id.value,
        )

    @pytest.mark.asyncio
    async def test_add_member_raises_for_workspace_not_found(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        user_id,
    ):
        """Test that add_member raises ValueError when workspace not found."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await workspace_service.add_member(
                workspace_id=WorkspaceId.generate(),
                acting_user_id=user_id,
                member_id="some-user-id",
                member_type=MemberType.USER,
                role=WorkspaceRole.MEMBER,
            )

    @pytest.mark.asyncio
    async def test_add_member_raises_for_different_tenant(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        user_id,
    ):
        """Test that add_member raises UnauthorizedError for cross-tenant workspace."""
        other_tenant_id = TenantId.generate()
        other_root = Workspace.create_root(name="Other", tenant_id=other_tenant_id)
        other_workspace = Workspace.create(
            name="Other WS",
            tenant_id=other_tenant_id,
            parent_workspace_id=other_root.id,
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=other_workspace)

        with pytest.raises(UnauthorizedError, match="different tenant"):
            await workspace_service.add_member(
                workspace_id=other_workspace.id,
                acting_user_id=user_id,
                member_id="some-user-id",
                member_type=MemberType.USER,
                role=WorkspaceRole.MEMBER,
            )

    @pytest.mark.asyncio
    async def test_remove_member_removes_user_from_workspace(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that remove_member successfully removes a user from workspace."""
        # Add member first
        member_id = UserId.generate().value
        child_workspace.add_member(member_id, MemberType.USER, WorkspaceRole.MEMBER)

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

        result = await workspace_service.remove_member(
            workspace_id=child_workspace.id,
            acting_user_id=user_id,
            member_id=member_id,
            member_type=MemberType.USER,
        )

        # Assert member was removed
        assert not result.has_member(member_id, MemberType.USER)

        # Assert repository save was called
        mock_workspace_repository.save.assert_called_once()

        # Assert probe was called
        mock_probe.workspace_member_removed.assert_called_once_with(
            workspace_id=child_workspace.id.value,
            member_id=member_id,
            member_type=MemberType.USER.value,
            acting_user_id=user_id.value,
        )

    @pytest.mark.asyncio
    async def test_remove_member_raises_for_workspace_not_found(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        user_id,
    ):
        """Test that remove_member raises ValueError when workspace not found."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await workspace_service.remove_member(
                workspace_id=WorkspaceId.generate(),
                acting_user_id=user_id,
                member_id="some-user-id",
                member_type=MemberType.USER,
            )

    @pytest.mark.asyncio
    async def test_remove_member_raises_for_different_tenant(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        user_id,
    ):
        """Test that remove_member raises UnauthorizedError for cross-tenant workspace."""
        other_tenant_id = TenantId.generate()
        other_root = Workspace.create_root(name="Other", tenant_id=other_tenant_id)
        other_workspace = Workspace.create(
            name="Other WS",
            tenant_id=other_tenant_id,
            parent_workspace_id=other_root.id,
        )
        member_id = "some-user-id"
        other_workspace.add_member(member_id, MemberType.USER, WorkspaceRole.MEMBER)

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=other_workspace)

        with pytest.raises(UnauthorizedError, match="different tenant"):
            await workspace_service.remove_member(
                workspace_id=other_workspace.id,
                acting_user_id=user_id,
                member_id=member_id,
                member_type=MemberType.USER,
            )

    @pytest.mark.asyncio
    async def test_list_members_returns_all_roles(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that list_members returns members across all three workspace roles."""
        mock_authz.check_permission = AsyncMock(return_value=True)

        ws_resource = f"workspace:{child_workspace.id.value}"

        # Simulate SpiceDB ReadRelationships returning explicit tuples
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=ws_resource,
                    relation="admin",
                    subject="user:user-admin-1",
                ),
                RelationshipTuple(
                    resource=ws_resource,
                    relation="editor",
                    subject="user:user-editor-1",
                ),
                RelationshipTuple(
                    resource=ws_resource,
                    relation="member",
                    subject="user:user-member-1",
                ),
            ]
        )

        result = await workspace_service.list_members(
            workspace_id=child_workspace.id,
            user_id=user_id,
        )

        assert len(result) == 3
        assert (
            WorkspaceAccessGrant(
                member_id="user-admin-1",
                member_type=MemberType.USER,
                role=WorkspaceRole.ADMIN,
            )
            in result
        )
        assert (
            WorkspaceAccessGrant(
                member_id="user-editor-1",
                member_type=MemberType.USER,
                role=WorkspaceRole.EDITOR,
            )
            in result
        )
        assert (
            WorkspaceAccessGrant(
                member_id="user-member-1",
                member_type=MemberType.USER,
                role=WorkspaceRole.MEMBER,
            )
            in result
        )

    @pytest.mark.asyncio
    async def test_list_members_includes_users_and_groups(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that list_members returns both user and group members."""
        mock_authz.check_permission = AsyncMock(return_value=True)

        ws_resource = f"workspace:{child_workspace.id.value}"

        # Simulate SpiceDB ReadRelationships returning explicit tuples
        # Groups are stored with #member subject relation in SpiceDB
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=ws_resource,
                    relation="admin",
                    subject="user:user-1",
                ),
                RelationshipTuple(
                    resource=ws_resource,
                    relation="admin",
                    subject="group:group-eng#member",
                ),
            ]
        )

        result = await workspace_service.list_members(
            workspace_id=child_workspace.id,
            user_id=user_id,
        )

        assert len(result) == 2
        assert (
            WorkspaceAccessGrant(
                member_id="user-1",
                member_type=MemberType.USER,
                role=WorkspaceRole.ADMIN,
            )
            in result
        )
        assert (
            WorkspaceAccessGrant(
                member_id="group-eng",
                member_type=MemberType.GROUP,
                role=WorkspaceRole.ADMIN,
            )
            in result
        )

    @pytest.mark.asyncio
    async def test_list_members_deduplicates_tuples(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that list_members deduplicates tuples returned by SpiceDB.

        ReadRelationships should not normally return duplicates, but the
        deduplication logic guards against it defensively.
        """
        mock_authz.check_permission = AsyncMock(return_value=True)

        ws_resource = f"workspace:{child_workspace.id.value}"

        # Simulate SpiceDB returning the same tuple twice (defensive case)
        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=ws_resource,
                    relation="admin",
                    subject="group:group-eng#member",
                ),
                RelationshipTuple(
                    resource=ws_resource,
                    relation="admin",
                    subject="group:group-eng#member",
                ),
            ]
        )

        result = await workspace_service.list_members(
            workspace_id=child_workspace.id,
            user_id=user_id,
        )

        # Should have exactly 1 entry, not 2
        assert len(result) == 1
        assert result[0] == WorkspaceAccessGrant(
            member_id="group-eng",
            member_type=MemberType.GROUP,
            role=WorkspaceRole.ADMIN,
        )

    @pytest.mark.asyncio
    async def test_add_member_validates_user_exists(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_user_repository,
        user_id,
        child_workspace,
    ):
        """Test that add_member validates the member_id refers to an existing user."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        # User does NOT exist
        mock_user_repository.get_by_id = AsyncMock(return_value=None)

        nonexistent_user_id = UserId.generate()

        with pytest.raises(ValueError, match="does not exist"):
            await workspace_service.add_member(
                workspace_id=child_workspace.id,
                acting_user_id=user_id,
                member_id=nonexistent_user_id.value,
                member_type=MemberType.USER,
                role=WorkspaceRole.MEMBER,
            )

    @pytest.mark.asyncio
    async def test_add_member_validates_group_exists(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_group_repository,
        user_id,
        child_workspace,
    ):
        """Test that add_member validates the member_id refers to an existing group."""
        from iam.domain.value_objects import GroupId

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        # Group does NOT exist
        mock_group_repository.get_by_id = AsyncMock(return_value=None)

        nonexistent_group_id = GroupId.generate()

        with pytest.raises(ValueError, match="does not exist"):
            await workspace_service.add_member(
                workspace_id=child_workspace.id,
                acting_user_id=user_id,
                member_id=nonexistent_group_id.value,
                member_type=MemberType.GROUP,
                role=WorkspaceRole.EDITOR,
            )

    @pytest.mark.asyncio
    async def test_add_member_succeeds_when_user_exists(
        self,
        mock_session,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that add_member succeeds when the user exists in the repository."""
        from iam.ports.repositories import IUserRepository, IGroupRepository

        mock_user_repo = create_autospec(IUserRepository, instance=True)
        mock_group_repo = create_autospec(IGroupRepository, instance=True)

        # User exists
        mock_user = MagicMock()
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        service = WorkspaceService(
            session=mock_session,
            workspace_repository=mock_workspace_repository,
            authz=mock_authz,
            scope_to_tenant=tenant_id,
            probe=mock_probe,
            user_repository=mock_user_repo,
            group_repository=mock_group_repo,
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

        new_member_id = UserId.generate()

        result = await service.add_member(
            workspace_id=child_workspace.id,
            acting_user_id=user_id,
            member_id=new_member_id.value,
            member_type=MemberType.USER,
            role=WorkspaceRole.MEMBER,
        )

        assert result.has_member(new_member_id.value, MemberType.USER)
        mock_user_repo.get_by_id.assert_called_once_with(new_member_id)

    @pytest.mark.asyncio
    async def test_add_member_succeeds_when_group_exists(
        self,
        mock_session,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that add_member succeeds when the group exists in the repository."""
        from iam.ports.repositories import IUserRepository, IGroupRepository
        from iam.domain.value_objects import GroupId

        mock_user_repo = create_autospec(IUserRepository, instance=True)
        mock_group_repo = create_autospec(IGroupRepository, instance=True)

        # Group exists
        mock_group = MagicMock()
        mock_group_repo.get_by_id = AsyncMock(return_value=mock_group)

        service = WorkspaceService(
            session=mock_session,
            workspace_repository=mock_workspace_repository,
            authz=mock_authz,
            scope_to_tenant=tenant_id,
            probe=mock_probe,
            user_repository=mock_user_repo,
            group_repository=mock_group_repo,
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

        new_group_id = GroupId.generate()

        result = await service.add_member(
            workspace_id=child_workspace.id,
            acting_user_id=user_id,
            member_id=new_group_id.value,
            member_type=MemberType.GROUP,
            role=WorkspaceRole.EDITOR,
        )

        assert result.has_member(new_group_id.value, MemberType.GROUP)
        mock_group_repo.get_by_id.assert_called_once_with(new_group_id)

    @pytest.mark.asyncio
    async def test_list_members_ignores_non_role_relations(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that list_members ignores tuples with non-role relations.

        ReadRelationships may return tuples for relations like 'parent' or
        'tenant' that are not workspace membership roles. These should be
        filtered out.
        """
        mock_authz.check_permission = AsyncMock(return_value=True)

        ws_resource = f"workspace:{child_workspace.id.value}"

        mock_authz.read_relationships = AsyncMock(
            return_value=[
                RelationshipTuple(
                    resource=ws_resource,
                    relation="admin",
                    subject="user:user-1",
                ),
                RelationshipTuple(
                    resource=ws_resource,
                    relation="parent",
                    subject="workspace:parent-ws",
                ),
            ]
        )

        result = await workspace_service.list_members(
            workspace_id=child_workspace.id,
            user_id=user_id,
        )

        # Should only include the admin tuple, not the parent relation
        assert len(result) == 1
        assert result[0] == WorkspaceAccessGrant(
            member_id="user-1",
            member_type=MemberType.USER,
            role=WorkspaceRole.ADMIN,
        )
