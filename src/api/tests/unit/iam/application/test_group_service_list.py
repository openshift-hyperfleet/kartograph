"""Unit tests for GroupService.list_groups().

Tests the application service layer for listing groups in a tenant
with VIEW permission filtering via SpiceDB lookup_resources.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest
from pytest_archon import archrule

from iam.application.services.group_service import GroupService
from iam.domain.aggregates import Group
from iam.domain.value_objects import TenantId, UserId
from iam.ports.repositories import IGroupRepository


class TestGroupServiceListArchitecturalBoundaries:
    """IAM application services must not depend on other bounded contexts."""

    def test_iam_application_does_not_import_graph(self):
        """IAM application layer should not depend on Graph context."""
        (
            archrule("iam_application_no_graph")
            .match("iam.application*")
            .should_not_import("graph*")
            .check("iam")
        )

    def test_iam_application_does_not_import_extraction(self):
        """IAM application layer should not depend on Extraction context."""
        (
            archrule("iam_application_no_extraction")
            .match("iam.application*")
            .should_not_import("extraction*")
            .check("iam")
        )

    def test_iam_application_does_not_import_management(self):
        """IAM application layer should not depend on Management context."""
        (
            archrule("iam_application_no_management")
            .match("iam.application*")
            .should_not_import("management*")
            .check("iam")
        )

    def test_iam_application_does_not_import_ingestion(self):
        """IAM application layer should not depend on Ingestion context."""
        (
            archrule("iam_application_no_ingestion")
            .match("iam.application*")
            .should_not_import("ingestion*")
            .check("iam")
        )

    def test_iam_application_does_not_import_querying(self):
        """IAM application layer should not depend on Querying context."""
        (
            archrule("iam_application_no_querying")
            .match("iam.application*")
            .should_not_import("query*")
            .check("iam")
        )


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
    """Tests for GroupService.list_groups() with VIEW permission filtering."""

    @pytest.mark.asyncio
    async def test_returns_view_filtered_groups(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Test that list_groups filters by VIEW permission via SpiceDB."""
        user_id = UserId.generate()
        group1 = Group.create(name="Engineering", tenant_id=tenant_id)
        group2 = Group.create(name="Marketing", tenant_id=tenant_id)
        group3 = Group.create(name="Secret", tenant_id=tenant_id)

        mock_group_repository.list_by_tenant = AsyncMock(
            return_value=[group1, group2, group3]
        )
        # User can only view group1 and group2
        mock_authz.lookup_resources = AsyncMock(
            return_value=[group1.id.value, group2.id.value]
        )

        groups = await group_service.list_groups(user_id=user_id)

        assert len(groups) == 2
        assert groups[0].name == "Engineering"
        assert groups[1].name == "Marketing"
        mock_group_repository.list_by_tenant.assert_called_once_with(
            tenant_id=tenant_id
        )
        mock_authz.lookup_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_groups(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Test that list_groups returns empty list when no groups exist."""
        user_id = UserId.generate()
        mock_group_repository.list_by_tenant = AsyncMock(return_value=[])
        mock_authz.lookup_resources = AsyncMock(return_value=[])

        groups = await group_service.list_groups(user_id=user_id)

        assert groups == []
        mock_group_repository.list_by_tenant.assert_called_once_with(
            tenant_id=tenant_id
        )

    @pytest.mark.asyncio
    async def test_returns_empty_when_user_has_no_view_access(
        self,
        group_service: GroupService,
        mock_group_repository,
        mock_authz,
        tenant_id,
    ):
        """Test that list_groups returns empty when user has no VIEW on any group."""
        user_id = UserId.generate()
        group1 = Group.create(name="Engineering", tenant_id=tenant_id)
        mock_group_repository.list_by_tenant = AsyncMock(return_value=[group1])
        # User has no VIEW access to any groups
        mock_authz.lookup_resources = AsyncMock(return_value=[])

        groups = await group_service.list_groups(user_id=user_id)

        assert groups == []
