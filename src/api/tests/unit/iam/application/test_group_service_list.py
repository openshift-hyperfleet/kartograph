"""Unit tests for GroupService.list_groups().

Tests the application service layer for listing groups in a tenant.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from iam.application.services.group_service import GroupService
from iam.domain.aggregates import Group
from iam.domain.value_objects import TenantId
from iam.ports.repositories import IGroupRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
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


class TestListGroups:
    """Tests for GroupService.list_groups()."""

    @pytest.mark.asyncio
    async def test_returns_all_groups_in_tenant(
        self,
        group_service: GroupService,
        mock_group_repository,
        tenant_id,
    ):
        """Test that list_groups returns all groups in the scoped tenant."""
        group1 = Group.create(name="Engineering", tenant_id=tenant_id)
        group2 = Group.create(name="Marketing", tenant_id=tenant_id)
        mock_group_repository.list_by_tenant = AsyncMock(return_value=[group1, group2])

        groups = await group_service.list_groups()

        assert len(groups) == 2
        assert groups[0].name == "Engineering"
        assert groups[1].name == "Marketing"
        mock_group_repository.list_by_tenant.assert_called_once_with(
            tenant_id=tenant_id
        )

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_groups(
        self,
        group_service: GroupService,
        mock_group_repository,
        tenant_id,
    ):
        """Test that list_groups returns empty list when no groups exist."""
        mock_group_repository.list_by_tenant = AsyncMock(return_value=[])

        groups = await group_service.list_groups()

        assert groups == []
        mock_group_repository.list_by_tenant.assert_called_once_with(
            tenant_id=tenant_id
        )
