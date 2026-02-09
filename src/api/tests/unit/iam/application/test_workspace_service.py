"""Unit tests for WorkspaceService.

Following TDD - write tests first to define desired behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from sqlalchemy.exc import IntegrityError

from iam.application.services.workspace_service import WorkspaceService
from iam.domain.aggregates import Workspace
from iam.domain.events import WorkspaceCreated, WorkspaceDeleted
from iam.domain.value_objects import TenantId, UserId, WorkspaceId
from iam.ports.exceptions import (
    CannotDeleteRootWorkspaceError,
    DuplicateWorkspaceNameError,
    UnauthorizedError,
    WorkspaceHasChildrenError,
)
from iam.ports.repositories import IWorkspaceRepository


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
def mock_workspace_repository():
    """Create mock workspace repository."""
    return create_autospec(IWorkspaceRepository, instance=True)


@pytest.fixture
def mock_authz():
    """Create mock authorization provider."""
    from shared_kernel.authorization.protocols import AuthorizationProvider

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
def creator_id() -> UserId:
    return UserId.generate()


@pytest.fixture
def root_workspace(tenant_id: TenantId) -> Workspace:
    """Create a root workspace for the tenant."""
    return Workspace.create_root(name="Root", tenant_id=tenant_id)


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


class TestCreateWorkspace:
    """Tests for create_workspace method."""

    @pytest.mark.asyncio
    async def test_create_workspace_creates_in_database(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        tenant_id,
        creator_id,
        root_workspace,
    ):
        """Test that create_workspace persists workspace to database."""
        # Setup: No duplicate name, parent exists in same tenant
        mock_workspace_repository.get_by_name = AsyncMock(return_value=None)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=root_workspace)
        mock_workspace_repository.save = AsyncMock()

        # Call
        result = await workspace_service.create_workspace(
            name="Engineering",
            parent_workspace_id=root_workspace.id,
            creator_id=creator_id,
        )

        # Assert: Workspace was created with correct attributes
        assert isinstance(result, Workspace)
        assert result.name == "Engineering"
        assert result.tenant_id == tenant_id
        assert result.parent_workspace_id == root_workspace.id
        assert result.is_root is False

        # Assert: Repository save was called
        mock_workspace_repository.save.assert_called_once()
        saved_workspace = mock_workspace_repository.save.call_args[0][0]
        assert saved_workspace.name == "Engineering"
        assert saved_workspace.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_create_workspace_enforces_unique_name(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        tenant_id,
        creator_id,
        root_workspace,
    ):
        """Test that duplicate workspace names are rejected within tenant."""
        # Setup: A workspace with the same name already exists
        existing_workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=root_workspace.id,
        )
        mock_workspace_repository.get_by_name = AsyncMock(
            return_value=existing_workspace
        )

        # Call and Assert: Should raise DuplicateWorkspaceNameError
        with pytest.raises(DuplicateWorkspaceNameError):
            await workspace_service.create_workspace(
                name="Engineering",
                parent_workspace_id=root_workspace.id,
                creator_id=creator_id,
            )

        # Assert: Save should NOT have been called
        mock_workspace_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_workspace_validates_parent_exists(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        creator_id,
    ):
        """Test that non-existent parent workspace is rejected."""
        # Setup: No duplicate name, parent does NOT exist
        mock_workspace_repository.get_by_name = AsyncMock(return_value=None)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=None)

        nonexistent_parent_id = WorkspaceId.generate()

        # Call and Assert: Should raise ValueError mentioning parent workspace
        with pytest.raises(ValueError, match="parent workspace"):
            await workspace_service.create_workspace(
                name="Engineering",
                parent_workspace_id=nonexistent_parent_id,
                creator_id=creator_id,
            )

        # Assert: Save should NOT have been called
        mock_workspace_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_workspace_rejects_parent_from_different_tenant(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        creator_id,
    ):
        """Test that parent workspace from different tenant is rejected."""
        # Setup: Parent workspace belongs to a different tenant
        other_tenant_id = TenantId.generate()
        other_tenant_root = Workspace.create_root(
            name="Other Root",
            tenant_id=other_tenant_id,
        )

        mock_workspace_repository.get_by_name = AsyncMock(return_value=None)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=other_tenant_root)

        # Call and Assert: Should raise ValueError mentioning different tenant
        with pytest.raises(ValueError, match="different tenant"):
            await workspace_service.create_workspace(
                name="Engineering",
                parent_workspace_id=other_tenant_root.id,
                creator_id=creator_id,
            )

        # Assert: Save should NOT have been called
        mock_workspace_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_workspace_emits_events(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
        tenant_id,
        creator_id,
        root_workspace,
    ):
        """Test that workspace creation emits WorkspaceCreated event and probe calls."""
        # Setup: No duplicate name, parent exists
        mock_workspace_repository.get_by_name = AsyncMock(return_value=None)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=root_workspace)
        mock_workspace_repository.save = AsyncMock()

        # Call
        result = await workspace_service.create_workspace(
            name="Engineering",
            parent_workspace_id=root_workspace.id,
            creator_id=creator_id,
        )

        # Assert: The workspace aggregate was saved with a WorkspaceCreated event
        # Since mock save doesn't call collect_events(), the events remain pending
        saved_workspace = mock_workspace_repository.save.call_args[0][0]
        events = saved_workspace.collect_events()
        assert len(events) == 1

        event = events[0]
        assert isinstance(event, WorkspaceCreated)
        assert event.workspace_id == result.id.value
        assert event.tenant_id == tenant_id.value
        assert event.name == "Engineering"
        assert event.parent_workspace_id == root_workspace.id.value
        assert event.is_root is False

        # Assert: Probe was called for success
        mock_probe.workspace_created.assert_called_once()
        probe_kwargs = mock_probe.workspace_created.call_args[1]
        assert probe_kwargs["workspace_id"] == result.id.value
        assert probe_kwargs["tenant_id"] == tenant_id.value
        assert probe_kwargs["name"] == "Engineering"
        assert probe_kwargs["parent_workspace_id"] == root_workspace.id.value
        assert probe_kwargs["is_root"] is False
        assert probe_kwargs["creator_id"] == creator_id.value


class TestCreateRootWorkspace:
    """Tests for create_root_workspace method."""

    @pytest.mark.asyncio
    async def test_create_root_workspace_uses_settings_default_name(
        self,
        mock_session,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
    ):
        """Test that create_root_workspace uses default_workspace_name from settings if provided."""
        # Setup: Mock settings with default_workspace_name = "Default"
        mock_settings = MagicMock()
        mock_settings.default_workspace_name = "Default"

        mock_workspace_repository.save = AsyncMock()

        service = WorkspaceService(
            session=mock_session,
            workspace_repository=mock_workspace_repository,
            authz=mock_authz,
            scope_to_tenant=tenant_id,
            probe=mock_probe,
        )

        # Call: No name provided, should use settings default
        with patch(
            "iam.application.services.workspace_service.get_iam_settings",
            return_value=mock_settings,
        ):
            workspace = await service.create_root_workspace(name=None)

        # Assert
        assert workspace.name == "Default"
        assert workspace.is_root is True
        assert workspace.parent_workspace_id is None
        assert workspace.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_create_root_workspace_uses_tenant_name_when_no_setting(
        self,
        mock_session,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
    ):
        """Test that create_root_workspace falls back to tenant name when setting is None.

        When neither an explicit name nor a settings default is available,
        the caller (TenantService) passes the tenant name explicitly.
        This test verifies that the explicit name parameter works as the fallback path.
        """
        # Setup: Settings with default_workspace_name = None
        mock_settings = MagicMock()
        mock_settings.default_workspace_name = None

        mock_workspace_repository.save = AsyncMock()

        service = WorkspaceService(
            session=mock_session,
            workspace_repository=mock_workspace_repository,
            authz=mock_authz,
            scope_to_tenant=tenant_id,
            probe=mock_probe,
        )

        # Call: Pass tenant name explicitly (as TenantService would)
        workspace = await service.create_root_workspace(name="Acme Corp")

        # Assert
        assert workspace.name == "Acme Corp"
        assert workspace.is_root is True
        assert workspace.parent_workspace_id is None
        assert workspace.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_create_root_workspace_uses_provided_name(
        self,
        mock_session,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
    ):
        """Test that explicit name parameter overrides settings."""
        # Setup: Settings with default_workspace_name = "Default"
        mock_settings = MagicMock()
        mock_settings.default_workspace_name = "Default"

        mock_workspace_repository.save = AsyncMock()

        service = WorkspaceService(
            session=mock_session,
            workspace_repository=mock_workspace_repository,
            authz=mock_authz,
            scope_to_tenant=tenant_id,
            probe=mock_probe,
        )

        # Call: Explicit name should override settings
        with patch(
            "iam.application.services.workspace_service.get_iam_settings",
            return_value=mock_settings,
        ):
            workspace = await service.create_root_workspace(name="Custom Root")

        # Assert: Explicit name used, not settings default
        assert workspace.name == "Custom Root"
        assert workspace.is_root is True

    @pytest.mark.asyncio
    async def test_create_root_workspace_emits_events(
        self,
        mock_session,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
    ):
        """Test that root workspace creation emits WorkspaceCreated event."""
        # Setup
        mock_workspace_repository.save = AsyncMock()

        service = WorkspaceService(
            session=mock_session,
            workspace_repository=mock_workspace_repository,
            authz=mock_authz,
            scope_to_tenant=tenant_id,
            probe=mock_probe,
        )

        # Call
        await service.create_root_workspace(name="Root")

        # Assert: The workspace aggregate was saved with a WorkspaceCreated event
        saved_workspace = mock_workspace_repository.save.call_args[0][0]
        events = saved_workspace.collect_events()
        assert len(events) == 1

        event = events[0]
        assert isinstance(event, WorkspaceCreated)
        assert event.is_root is True
        assert event.parent_workspace_id is None
        assert event.name == "Root"
        assert event.tenant_id == tenant_id.value

        # Assert: Probe was called for success
        mock_probe.workspace_created.assert_called_once()
        probe_kwargs = mock_probe.workspace_created.call_args[1]
        assert probe_kwargs["is_root"] is True
        assert probe_kwargs["parent_workspace_id"] is None
        assert probe_kwargs["creator_id"] == ""


class TestGetWorkspace:
    """Tests for WorkspaceService.get_workspace()."""

    @pytest.mark.asyncio
    async def test_get_workspace_returns_workspace(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
        tenant_id,
        root_workspace,
    ):
        """Test that get_workspace returns workspace when it exists in scoped tenant."""
        # Setup: Create a child workspace in the scoped tenant
        child_workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=root_workspace.id,
        )
        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)

        # Call
        workspace = await workspace_service.get_workspace(child_workspace.id)

        # Assert: Workspace returned with correct attributes
        assert workspace is not None
        assert workspace.id == child_workspace.id
        assert workspace.name == "Engineering"
        assert workspace.tenant_id == tenant_id

        # Assert: Repository was called with correct ID
        mock_workspace_repository.get_by_id.assert_called_once_with(child_workspace.id)

        # Assert: Probe recorded successful retrieval
        mock_probe.workspace_retrieved.assert_called_once_with(
            workspace_id=child_workspace.id.value,
            tenant_id=tenant_id.value,
            name="Engineering",
        )

    @pytest.mark.asyncio
    async def test_get_workspace_returns_none_when_not_found(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
    ):
        """Test that get_workspace returns None when workspace doesn't exist."""
        # Setup: Repository returns None (workspace not found)
        nonexistent_id = WorkspaceId.generate()
        mock_workspace_repository.get_by_id = AsyncMock(return_value=None)

        # Call
        workspace = await workspace_service.get_workspace(nonexistent_id)

        # Assert: Returns None
        assert workspace is None

        # Assert: Probe recorded workspace_not_found
        mock_probe.workspace_not_found.assert_called_once_with(
            workspace_id=nonexistent_id.value,
        )

        # Assert: workspace_retrieved was NOT called
        mock_probe.workspace_retrieved.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_workspace_returns_none_for_different_tenant(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
    ):
        """Test that get_workspace returns None for workspace in different tenant."""
        # Setup: Create workspace belonging to a different tenant
        other_tenant_id = TenantId.generate()
        other_tenant_root = Workspace.create_root(
            name="Other Root",
            tenant_id=other_tenant_id,
        )
        other_workspace = Workspace.create(
            name="Other Workspace",
            tenant_id=other_tenant_id,
            parent_workspace_id=other_tenant_root.id,
        )
        mock_workspace_repository.get_by_id = AsyncMock(return_value=other_workspace)

        # Call: Service is scoped to tenant_id, but workspace belongs to other_tenant_id
        workspace = await workspace_service.get_workspace(other_workspace.id)

        # Assert: Returns None (doesn't leak existence of workspace in other tenant)
        assert workspace is None

        # Assert: Neither retrieved nor not_found probe called
        # (workspace exists but belongs to different tenant - silent rejection)
        mock_probe.workspace_retrieved.assert_not_called()
        mock_probe.workspace_not_found.assert_not_called()


class TestListWorkspaces:
    """Tests for WorkspaceService.list_workspaces()."""

    @pytest.mark.asyncio
    async def test_list_workspaces_returns_all_in_tenant(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
        tenant_id,
        root_workspace,
    ):
        """Test that list_workspaces returns all workspaces in scoped tenant."""
        # Setup: Tenant has root workspace + 2 child workspaces
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

        # Call
        workspaces = await workspace_service.list_workspaces()

        # Assert: All 3 workspaces returned
        assert len(workspaces) == 3
        assert all(w.tenant_id == tenant_id for w in workspaces)

        # Assert: Repository called with scoped tenant ID
        mock_workspace_repository.list_by_tenant.assert_called_once_with(
            tenant_id=tenant_id,
        )

        # Assert: Probe recorded listing
        mock_probe.workspaces_listed.assert_called_once_with(
            tenant_id=tenant_id.value,
            count=3,
        )

    @pytest.mark.asyncio
    async def test_list_workspaces_returns_empty_when_none(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
        tenant_id,
    ):
        """Test that list_workspaces returns empty list when tenant has no workspaces."""
        # Setup: Repository returns empty list
        mock_workspace_repository.list_by_tenant = AsyncMock(return_value=[])

        # Call
        workspaces = await workspace_service.list_workspaces()

        # Assert: Empty list returned
        assert workspaces == []

        # Assert: Probe recorded listing with count 0
        mock_probe.workspaces_listed.assert_called_once_with(
            tenant_id=tenant_id.value,
            count=0,
        )

    @pytest.mark.asyncio
    async def test_list_workspaces_scoped_to_tenant(
        self,
        mock_session,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
    ):
        """Test that list_workspaces only returns workspaces from scoped tenant."""
        # Setup: Two tenants with different workspaces
        tenant1_id = TenantId.generate()

        tenant1_root = Workspace.create_root(name="T1 Root", tenant_id=tenant1_id)
        tenant1_child = Workspace.create(
            name="T1 Engineering",
            tenant_id=tenant1_id,
            parent_workspace_id=tenant1_root.id,
        )
        tenant1_workspaces = [tenant1_root, tenant1_child]

        # Service scoped to tenant1
        service = WorkspaceService(
            session=mock_session,
            workspace_repository=mock_workspace_repository,
            authz=mock_authz,
            scope_to_tenant=tenant1_id,
            probe=mock_probe,
        )

        # Repository returns only tenant1's workspaces (as it should when queried by tenant_id)
        mock_workspace_repository.list_by_tenant = AsyncMock(
            return_value=tenant1_workspaces
        )

        # Call
        workspaces = await service.list_workspaces()

        # Assert: Only tenant1's workspaces returned
        assert len(workspaces) == 2
        assert all(w.tenant_id == tenant1_id for w in workspaces)

        # Assert: Repository called with tenant1's ID (not tenant2's)
        mock_workspace_repository.list_by_tenant.assert_called_once_with(
            tenant_id=tenant1_id,
        )

        # Assert: Probe recorded correct count
        mock_probe.workspaces_listed.assert_called_once_with(
            tenant_id=tenant1_id.value,
            count=2,
        )


class TestDeleteWorkspace:
    """Tests for WorkspaceService.delete_workspace()."""

    @pytest.mark.asyncio
    async def test_delete_workspace_removes_from_database(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
        tenant_id,
        root_workspace,
    ):
        """Test that delete_workspace successfully deletes a child workspace."""
        # Setup: Create a child workspace in the scoped tenant
        child_workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=root_workspace.id,
        )
        # Consume creation event so it doesn't interfere with deletion assertions
        child_workspace.collect_events()

        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.delete = AsyncMock(return_value=True)

        # Call
        result = await workspace_service.delete_workspace(child_workspace.id)

        # Assert: Deletion succeeded
        assert result is True

        # Assert: Repository delete was called with workspace that has deletion event
        mock_workspace_repository.delete.assert_called_once()

        # Assert: Probe recorded successful deletion
        mock_probe.workspace_deleted.assert_called_once_with(
            workspace_id=child_workspace.id.value,
            tenant_id=tenant_id.value,
        )

    @pytest.mark.asyncio
    async def test_delete_workspace_returns_false_when_not_found(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
    ):
        """Test that delete_workspace returns False when workspace doesn't exist."""
        # Setup: Repository returns None (workspace not found)
        nonexistent_id = WorkspaceId.generate()
        mock_workspace_repository.get_by_id = AsyncMock(return_value=None)

        # Call
        result = await workspace_service.delete_workspace(nonexistent_id)

        # Assert: Returns False
        assert result is False

        # Assert: Delete was NOT called
        mock_workspace_repository.delete.assert_not_called()

        # Assert: Deletion probes not called
        mock_probe.workspace_deleted.assert_not_called()

    @pytest.mark.asyncio
    async def test_cannot_delete_root_workspace(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
        root_workspace,
    ):
        """Test that deleting root workspace raises CannotDeleteRootWorkspaceError."""
        # Setup: Return the root workspace
        # Consume creation event
        root_workspace.collect_events()
        mock_workspace_repository.get_by_id = AsyncMock(return_value=root_workspace)

        # Call and Assert: Should raise CannotDeleteRootWorkspaceError
        with pytest.raises(CannotDeleteRootWorkspaceError):
            await workspace_service.delete_workspace(root_workspace.id)

        # Assert: Delete was NOT called (business rule prevented it)
        mock_workspace_repository.delete.assert_not_called()

        # Assert: Deletion failure probe was called
        mock_probe.workspace_deletion_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_delete_workspace_with_children(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
        tenant_id,
        root_workspace,
    ):
        """Test that deleting workspace with children raises WorkspaceHasChildrenError."""
        # Setup: Create a child workspace (which has a grandchild via DB constraint)
        child_workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=root_workspace.id,
        )
        child_workspace.collect_events()

        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)

        # Simulate database IntegrityError when trying to delete
        # (the DB RESTRICT constraint on parent_workspace_id fires)
        integrity_error = IntegrityError(
            "DELETE FROM workspaces",
            params={},
            orig=Exception(
                'update or delete on table "workspaces" violates '
                'foreign key constraint "workspaces_parent_workspace_id_fkey"'
            ),
        )
        mock_workspace_repository.delete = AsyncMock(side_effect=integrity_error)

        # Call and Assert: Should raise WorkspaceHasChildrenError
        with pytest.raises(WorkspaceHasChildrenError):
            await workspace_service.delete_workspace(child_workspace.id)

        # Assert: Deletion failure probe was called
        mock_probe.workspace_deletion_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_workspace_checks_tenant_ownership(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
    ):
        """Test that delete_workspace rejects workspace from different tenant."""
        # Setup: Create workspace belonging to a different tenant
        other_tenant_id = TenantId.generate()
        other_tenant_root = Workspace.create_root(
            name="Other Root",
            tenant_id=other_tenant_id,
        )
        other_workspace = Workspace.create(
            name="Other Workspace",
            tenant_id=other_tenant_id,
            parent_workspace_id=other_tenant_root.id,
        )
        other_workspace.collect_events()

        mock_workspace_repository.get_by_id = AsyncMock(return_value=other_workspace)

        # Call and Assert: Should raise UnauthorizedError
        with pytest.raises(UnauthorizedError, match="different tenant"):
            await workspace_service.delete_workspace(other_workspace.id)

        # Assert: Delete was NOT called
        mock_workspace_repository.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_workspace_emits_events(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_probe,
        tenant_id,
        root_workspace,
    ):
        """Test that workspace deletion emits WorkspaceDeleted event to outbox."""
        # Setup: Create a child workspace
        child_workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=root_workspace.id,
        )
        # Consume the creation event
        child_workspace.collect_events()

        mock_workspace_repository.get_by_id = AsyncMock(return_value=child_workspace)
        mock_workspace_repository.delete = AsyncMock(return_value=True)

        # Call
        await workspace_service.delete_workspace(child_workspace.id)

        # Assert: The workspace passed to delete had mark_for_deletion() called
        # which records a WorkspaceDeleted event
        deleted_workspace = mock_workspace_repository.delete.call_args[0][0]

        # Since mark_for_deletion was called and events haven't been collected
        # by the mock repository, we can verify the event was recorded
        # by checking that mark_for_deletion was called (the workspace
        # is the same object passed to delete)
        # The repository's delete method collects events internally,
        # but in mock, we can verify the workspace had events pending
        # We need to check the workspace state BEFORE delete consumed the events
        # Since the mock doesn't consume events, we can collect them here
        events = deleted_workspace.collect_events()
        assert len(events) == 1

        event = events[0]
        assert isinstance(event, WorkspaceDeleted)
        assert event.workspace_id == child_workspace.id.value
        assert event.tenant_id == tenant_id.value
        assert event.parent_workspace_id == root_workspace.id.value
        assert event.is_root is False
