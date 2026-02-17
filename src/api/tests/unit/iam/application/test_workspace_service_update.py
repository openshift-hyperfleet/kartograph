"""Unit tests for WorkspaceService.update_workspace().

Tests the application service layer for updating workspace metadata (rename).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from iam.application.services.workspace_service import WorkspaceService
from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId, UserId, WorkspaceId
from iam.ports.exceptions import DuplicateWorkspaceNameError, UnauthorizedError
from iam.ports.repositories import IWorkspaceRepository


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
def user_id() -> UserId:
    return UserId.generate()


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


class TestUpdateWorkspace:
    """Tests for WorkspaceService.update_workspace()."""

    @pytest.mark.asyncio
    async def test_renames_workspace_successfully(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        tenant_id,
        user_id,
    ):
        """Test that update_workspace renames the workspace."""
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=WorkspaceId.generate(),
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=workspace)
        mock_workspace_repository.get_by_name = AsyncMock(return_value=None)
        mock_workspace_repository.save = AsyncMock()

        result = await workspace_service.update_workspace(
            workspace_id=workspace.id,
            user_id=user_id,
            name="Platform Engineering",
        )

        assert result.name == "Platform Engineering"
        mock_workspace_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_permission_error_when_no_manage(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        user_id,
    ):
        """Test that update_workspace raises PermissionError without MANAGE permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(PermissionError, match="lacks manage permission"):
            await workspace_service.update_workspace(
                workspace_id=WorkspaceId.generate(),
                user_id=user_id,
                name="New Name",
            )

    @pytest.mark.asyncio
    async def test_raises_value_error_when_workspace_not_found(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        user_id,
    ):
        """Test that update_workspace raises ValueError for missing workspace."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await workspace_service.update_workspace(
                workspace_id=WorkspaceId.generate(),
                user_id=user_id,
                name="New Name",
            )

    @pytest.mark.asyncio
    async def test_raises_unauthorized_for_different_tenant(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        user_id,
    ):
        """Test that update_workspace raises UnauthorizedError for different tenant."""
        other_tenant = TenantId.generate()
        workspace = Workspace.create(
            name="Other Workspace",
            tenant_id=other_tenant,
            parent_workspace_id=WorkspaceId.generate(),
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=workspace)

        with pytest.raises(UnauthorizedError, match="different tenant"):
            await workspace_service.update_workspace(
                workspace_id=workspace.id,
                user_id=user_id,
                name="New Name",
            )

    @pytest.mark.asyncio
    async def test_raises_duplicate_name_error(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        tenant_id,
        user_id,
    ):
        """Test that update_workspace raises DuplicateWorkspaceNameError when name exists."""
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=WorkspaceId.generate(),
        )
        existing = Workspace.create(
            name="Marketing",
            tenant_id=tenant_id,
            parent_workspace_id=WorkspaceId.generate(),
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=workspace)
        mock_workspace_repository.get_by_name = AsyncMock(return_value=existing)

        with pytest.raises(DuplicateWorkspaceNameError, match="already exists"):
            await workspace_service.update_workspace(
                workspace_id=workspace.id,
                user_id=user_id,
                name="Marketing",
            )

    @pytest.mark.asyncio
    async def test_skips_uniqueness_check_when_name_unchanged(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        tenant_id,
        user_id,
    ):
        """Test that update_workspace skips uniqueness check when name is the same."""
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=WorkspaceId.generate(),
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=workspace)
        mock_workspace_repository.save = AsyncMock()

        # Renaming to same name will raise ValueError from aggregate (name unchanged)
        with pytest.raises(ValueError, match="same as current name"):
            await workspace_service.update_workspace(
                workspace_id=workspace.id,
                user_id=user_id,
                name="Engineering",
            )
