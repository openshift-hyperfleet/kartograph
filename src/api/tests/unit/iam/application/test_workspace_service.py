"""Unit tests for WorkspaceService.create_workspace.

Following TDD - write tests first to define desired behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, create_autospec

from iam.application.services.workspace_service import WorkspaceService
from iam.domain.aggregates import Workspace
from iam.domain.events import WorkspaceCreated
from iam.domain.value_objects import TenantId, UserId, WorkspaceId
from iam.ports.exceptions import DuplicateWorkspaceNameError
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
