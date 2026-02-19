"""Unit tests for WorkspaceService.update_member_role().

Tests the application service layer for updating a workspace member's role.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from iam.application.services.workspace_service import WorkspaceService
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
def acting_user_id() -> UserId:
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


class TestUpdateMemberRole:
    """Tests for WorkspaceService.update_member_role()."""

    @pytest.mark.asyncio
    async def test_updates_role_successfully(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        mock_probe,
        tenant_id,
        acting_user_id,
    ):
        """Test that update_member_role updates a member's role."""
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=WorkspaceId.generate(),
        )
        workspace.add_member("alice-id", MemberType.USER, WorkspaceRole.MEMBER)

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=workspace)
        mock_workspace_repository.save = AsyncMock()

        result = await workspace_service.update_member_role(
            workspace_id=workspace.id,
            acting_user_id=acting_user_id,
            member_id="alice-id",
            member_type=MemberType.USER,
            new_role=WorkspaceRole.ADMIN,
        )

        assert result is workspace
        mock_workspace_repository.save.assert_called_once()
        mock_probe.workspace_member_role_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_permission_error_when_no_manage(
        self,
        workspace_service: WorkspaceService,
        mock_authz,
        acting_user_id,
    ):
        """Test that update_member_role raises UnauthorizedError without MANAGE permission."""
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError, match="lacks manage permission"):
            await workspace_service.update_member_role(
                workspace_id=WorkspaceId.generate(),
                acting_user_id=acting_user_id,
                member_id="alice-id",
                member_type=MemberType.USER,
                new_role=WorkspaceRole.ADMIN,
            )

    @pytest.mark.asyncio
    async def test_raises_value_error_when_workspace_not_found(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        acting_user_id,
    ):
        """Test that update_member_role raises ValueError for missing workspace."""
        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await workspace_service.update_member_role(
                workspace_id=WorkspaceId.generate(),
                acting_user_id=acting_user_id,
                member_id="alice-id",
                member_type=MemberType.USER,
                new_role=WorkspaceRole.ADMIN,
            )

    @pytest.mark.asyncio
    async def test_raises_unauthorized_for_different_tenant(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        acting_user_id,
    ):
        """Test that update_member_role raises UnauthorizedError for different tenant."""
        other_tenant = TenantId.generate()
        workspace = Workspace.create(
            name="Other Workspace",
            tenant_id=other_tenant,
            parent_workspace_id=WorkspaceId.generate(),
        )

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=workspace)

        with pytest.raises(UnauthorizedError, match="different tenant"):
            await workspace_service.update_member_role(
                workspace_id=workspace.id,
                acting_user_id=acting_user_id,
                member_id="alice-id",
                member_type=MemberType.USER,
                new_role=WorkspaceRole.ADMIN,
            )

    @pytest.mark.asyncio
    async def test_raises_value_error_when_role_unchanged(
        self,
        workspace_service: WorkspaceService,
        mock_workspace_repository,
        mock_authz,
        tenant_id,
        acting_user_id,
    ):
        """Test that update_member_role raises ValueError when role is the same."""
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=WorkspaceId.generate(),
        )
        workspace.add_member("alice-id", MemberType.USER, WorkspaceRole.ADMIN)

        mock_authz.check_permission = AsyncMock(return_value=True)
        mock_workspace_repository.get_by_id = AsyncMock(return_value=workspace)

        with pytest.raises(ValueError, match="already has role"):
            await workspace_service.update_member_role(
                workspace_id=workspace.id,
                acting_user_id=acting_user_id,
                member_id="alice-id",
                member_type=MemberType.USER,
                new_role=WorkspaceRole.ADMIN,
            )
