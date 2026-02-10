"""Unit tests for TenantBootstrapService (TDD).

Following TDD: Write tests that describe the desired behavior,
then implement the TenantBootstrapService to make these tests pass.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.services import TenantBootstrapService
from iam.domain.aggregates import Tenant, Workspace
from iam.domain.value_objects import TenantId, WorkspaceId
from iam.ports.exceptions import DuplicateTenantNameError
from iam.ports.repositories import ITenantRepository, IWorkspaceRepository
from infrastructure.observability.startup_probe import StartupProbe


@pytest.fixture
def mock_tenant_repo():
    """Mock TenantRepository."""
    return Mock(spec=ITenantRepository)


@pytest.fixture
def mock_workspace_repo():
    """Mock WorkspaceRepository."""
    return Mock(spec=IWorkspaceRepository)


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
def mock_probe():
    """Mock StartupProbe."""
    return Mock(spec=StartupProbe)


@pytest.fixture
def bootstrap_service(
    mock_tenant_repo,
    mock_workspace_repo,
    mock_session,
    mock_probe,
):
    """Create TenantBootstrapService with mocked dependencies."""
    return TenantBootstrapService(
        tenant_repository=mock_tenant_repo,
        workspace_repository=mock_workspace_repo,
        session=mock_session,
        probe=mock_probe,
    )


class TestEnsureDefaultTenantWithWorkspace:
    """Tests for TenantBootstrapService.ensure_default_tenant_with_workspace()."""

    @pytest.mark.asyncio
    async def test_creates_tenant_and_workspace_when_neither_exist(
        self, bootstrap_service, mock_tenant_repo, mock_workspace_repo, mock_probe
    ):
        """Test that both tenant and root workspace are created when tenant doesn't exist."""
        mock_tenant_repo.get_by_name = AsyncMock(return_value=None)
        mock_tenant_repo.save = AsyncMock()
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=None)
        mock_workspace_repo.save = AsyncMock()

        tenant = await bootstrap_service.ensure_default_tenant_with_workspace(
            tenant_name="default",
            workspace_name="Root",
        )

        # Verify tenant was created and saved
        assert tenant.name == "default"
        mock_tenant_repo.save.assert_called_once()

        # Verify root workspace was created and saved
        mock_workspace_repo.save.assert_called_once()
        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        assert saved_workspace.is_root is True
        assert saved_workspace.tenant_id == tenant.id
        assert saved_workspace.name == "Root"

        # Verify probe events
        mock_probe.default_tenant_bootstrapped.assert_called_once()
        mock_probe.default_workspace_bootstrapped.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_workspace_when_tenant_exists_without_workspace(
        self, bootstrap_service, mock_tenant_repo, mock_workspace_repo, mock_probe
    ):
        """Test that root workspace is created when tenant exists but has no workspace."""
        existing_tenant = Tenant(id=TenantId.generate(), name="default")

        mock_tenant_repo.get_by_name = AsyncMock(return_value=existing_tenant)
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=None)
        mock_workspace_repo.save = AsyncMock()

        tenant = await bootstrap_service.ensure_default_tenant_with_workspace(
            tenant_name="default",
            workspace_name="Root",
        )

        # Verify tenant was not created (returned existing)
        assert tenant.id == existing_tenant.id
        mock_tenant_repo.save.assert_not_called()

        # Verify root workspace was created
        mock_workspace_repo.save.assert_called_once()
        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        assert saved_workspace.is_root is True
        assert saved_workspace.tenant_id == existing_tenant.id

        # Verify probe events
        mock_probe.default_tenant_already_exists.assert_called_once()
        mock_probe.default_workspace_bootstrapped.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_nothing_when_tenant_and_workspace_exist(
        self, bootstrap_service, mock_tenant_repo, mock_workspace_repo, mock_probe
    ):
        """Test that no creation occurs when both tenant and workspace exist."""
        from datetime import UTC, datetime

        existing_tenant = Tenant(id=TenantId.generate(), name="default")
        existing_workspace = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=existing_tenant.id,
            name="Root",
            parent_workspace_id=None,
            is_root=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_tenant_repo.get_by_name = AsyncMock(return_value=existing_tenant)
        mock_workspace_repo.get_root_workspace = AsyncMock(
            return_value=existing_workspace
        )

        tenant = await bootstrap_service.ensure_default_tenant_with_workspace(
            tenant_name="default",
            workspace_name="Root",
        )

        # Verify neither was created
        assert tenant.id == existing_tenant.id
        mock_tenant_repo.save.assert_not_called()
        mock_workspace_repo.save.assert_not_called()

        # Verify probe events
        mock_probe.default_tenant_already_exists.assert_called_once()
        mock_probe.default_workspace_already_exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_race_condition_on_tenant_creation(
        self, bootstrap_service, mock_tenant_repo, mock_workspace_repo, mock_probe
    ):
        """Test that race conditions during concurrent startup are handled."""
        from datetime import UTC, datetime

        # First get_by_name returns None, then after DuplicateTenantNameError
        # it returns the tenant created by another process
        concurrent_tenant = Tenant(id=TenantId.generate(), name="default")
        existing_workspace = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=concurrent_tenant.id,
            name="Root",
            parent_workspace_id=None,
            is_root=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_tenant_repo.get_by_name = AsyncMock(side_effect=[None, concurrent_tenant])
        mock_tenant_repo.save = AsyncMock(
            side_effect=DuplicateTenantNameError("default")
        )
        mock_workspace_repo.get_root_workspace = AsyncMock(
            return_value=existing_workspace
        )

        tenant = await bootstrap_service.ensure_default_tenant_with_workspace(
            tenant_name="default",
            workspace_name="Root",
        )

        # Should return the tenant created by the concurrent process
        assert tenant.id == concurrent_tenant.id

        # Verify the re-query happened
        assert mock_tenant_repo.get_by_name.call_count == 2

        # Probe should record the race condition scenario
        mock_probe.default_tenant_already_exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_unrecoverable_race_condition(
        self, bootstrap_service, mock_tenant_repo, mock_workspace_repo
    ):
        """Test that RuntimeError is raised if tenant cannot be created or retrieved."""
        mock_tenant_repo.get_by_name = AsyncMock(return_value=None)
        mock_tenant_repo.save = AsyncMock(
            side_effect=DuplicateTenantNameError("default")
        )

        with pytest.raises(RuntimeError) as exc_info:
            await bootstrap_service.ensure_default_tenant_with_workspace(
                tenant_name="default",
                workspace_name="Root",
            )

        assert "Failed to create or retrieve default tenant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_uses_workspace_name_from_parameter(
        self, bootstrap_service, mock_tenant_repo, mock_workspace_repo, mock_probe
    ):
        """Test that workspace name is taken from parameter."""
        mock_tenant_repo.get_by_name = AsyncMock(return_value=None)
        mock_tenant_repo.save = AsyncMock()
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=None)
        mock_workspace_repo.save = AsyncMock()

        await bootstrap_service.ensure_default_tenant_with_workspace(
            tenant_name="default",
            workspace_name="Custom Workspace",
        )

        saved_workspace = mock_workspace_repo.save.call_args[0][0]
        assert saved_workspace.name == "Custom Workspace"

    @pytest.mark.asyncio
    async def test_returns_tenant_id_for_caching(
        self, bootstrap_service, mock_tenant_repo, mock_workspace_repo, mock_probe
    ):
        """Test that the method returns the tenant for ID caching."""
        mock_tenant_repo.get_by_name = AsyncMock(return_value=None)
        mock_tenant_repo.save = AsyncMock()
        mock_workspace_repo.get_root_workspace = AsyncMock(return_value=None)
        mock_workspace_repo.save = AsyncMock()

        tenant = await bootstrap_service.ensure_default_tenant_with_workspace(
            tenant_name="default",
            workspace_name="Root",
        )

        # Tenant should have a valid ID
        assert tenant.id is not None
        assert isinstance(tenant.id, TenantId)
