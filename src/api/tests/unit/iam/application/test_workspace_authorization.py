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
from iam.ports.repositories import IWorkspaceRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    SubjectRelation,
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
    tenant_id,
):
    """Create WorkspaceService with mock dependencies."""
    return WorkspaceService(
        session=mock_session,
        workspace_repository=mock_workspace_repository,
        authz=mock_authz,
        scope_to_tenant=tenant_id,
        probe=mock_probe,
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
        # Return empty for all role lookups
        mock_authz.lookup_subjects = AsyncMock(return_value=[])

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
        """Test that list_members raises PermissionError without VIEW permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks view permission"):
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
        """Test that delete_workspace raises PermissionError without MANAGE permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission"):
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
        """Test that create_workspace checks MANAGE permission on parent workspace."""
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

        # Verify MANAGE permission was checked on parent workspace
        mock_authz.check_permission.assert_called_once_with(
            resource=format_resource(ResourceType.WORKSPACE, root_workspace.id.value),
            permission=Permission.MANAGE.value,
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
        """Test that create_workspace raises PermissionError without MANAGE on parent."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission on parent"):
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
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that add_member checks MANAGE permission before adding."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

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
        """Test that add_member raises PermissionError without MANAGE permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission"):
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
        """Test that remove_member raises PermissionError without MANAGE permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission"):
            await workspace_service.remove_member(
                workspace_id=child_workspace.id,
                acting_user_id=user_id,
                member_id="some-user-id",
                member_type=MemberType.USER,
            )


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
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that add_member successfully adds a user member to workspace."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

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
        tenant_id,
        user_id,
        child_workspace,
    ):
        """Test that add_member successfully adds a group member to workspace."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.save = AsyncMock()

        group_id = "group-eng-team"

        result = await workspace_service.add_member(
            workspace_id=child_workspace.id,
            acting_user_id=user_id,
            member_id=group_id,
            member_type=MemberType.GROUP,
            role=WorkspaceRole.ADMIN,
        )

        assert result.has_member(group_id, MemberType.GROUP)
        assert result.get_member_role(group_id, MemberType.GROUP) == WorkspaceRole.ADMIN

        mock_probe.workspace_member_added.assert_called_once_with(
            workspace_id=child_workspace.id.value,
            member_id=group_id,
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

        # Simulate SpiceDB responses for each role
        admin_users = [
            SubjectRelation(subject_id="user-admin-1", relation="admin"),
        ]
        admin_groups: list[SubjectRelation] = []
        editor_users = [
            SubjectRelation(subject_id="user-editor-1", relation="editor"),
        ]
        editor_groups: list[SubjectRelation] = []
        member_users = [
            SubjectRelation(subject_id="user-member-1", relation="member"),
        ]
        member_groups: list[SubjectRelation] = []

        # lookup_subjects is called 6 times: for each of 3 roles x 2 subject types
        mock_authz.lookup_subjects = AsyncMock(
            side_effect=[
                admin_users,  # admin + USER
                admin_groups,  # admin + GROUP
                editor_users,  # editor + USER
                editor_groups,  # editor + GROUP
                member_users,  # member + USER
                member_groups,  # member + GROUP
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

        admin_users = [
            SubjectRelation(subject_id="user-1", relation="admin"),
        ]
        admin_groups = [
            SubjectRelation(subject_id="group-eng", relation="admin"),
        ]

        # All other role lookups return empty
        mock_authz.lookup_subjects = AsyncMock(
            side_effect=[
                admin_users,  # admin + USER
                admin_groups,  # admin + GROUP
                [],  # editor + USER
                [],  # editor + GROUP
                [],  # member + USER
                [],  # member + GROUP
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
    async def test_list_members_deduplicates_groups(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
        child_workspace,
    ):
        """Test that list_members deduplicates groups returned by SpiceDB.

        SpiceDB's LookupSubjects can return the same group multiple times
        when the subject relation (group#member) resolves through multiple
        permission paths (e.g., member = admin + member_relation). This
        test verifies the deduplication logic.
        """
        mock_authz.check_permission = AsyncMock(return_value=True)

        # Simulate SpiceDB returning the same group twice for the admin role
        # (due to member permission resolving through both admin and member_relation)
        admin_groups_with_duplicates = [
            SubjectRelation(subject_id="group-eng", relation="admin"),
            SubjectRelation(subject_id="group-eng", relation="admin"),
        ]

        mock_authz.lookup_subjects = AsyncMock(
            side_effect=[
                [],  # admin + USER
                admin_groups_with_duplicates,  # admin + GROUP (with duplicate)
                [],  # editor + USER
                [],  # editor + GROUP
                [],  # member + USER
                [],  # member + GROUP
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
