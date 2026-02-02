"""Unit tests for TenantService (TDD).

Following TDD: Write tests that describe the desired behavior,
then implement the TenantService to make these tests pass.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.services import TenantService
from iam.domain.aggregates import Tenant
from iam.domain.value_objects import TenantId, TenantRole, UserId
from iam.ports.exceptions import UnauthorizedError
from iam.ports.repositories import (
    IAPIKeyRepository,
    IGroupRepository,
    ITenantRepository,
)
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import SubjectRelation


@pytest.fixture
def mock_tenant_repo():
    """Mock TenantRepository."""
    return Mock(spec=ITenantRepository)


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
    mock_tenant_repo, mock_group_repo, mock_api_key_repo, mock_authz, mock_session
):
    """Create TenantService with mocked dependencies."""
    return TenantService(
        tenant_repository=mock_tenant_repo,
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


class TestListMembers:
    """Tests for TenantService.list_members()."""

    @pytest.mark.asyncio
    async def test_lists_members_from_spicedb(
        self, tenant_service, mock_tenant_repo, mock_authz
    ):
        """Test that list_members queries SpiceDB for tenant members."""
        tenant_id = TenantId.generate()
        requesting_user_id = UserId.from_string("admin-456")

        # Mock authorization check
        mock_authz.check_permission = AsyncMock(return_value=True)

        # Mock tenant existence
        tenant = Tenant(id=tenant_id, name="Acme Corp")
        mock_tenant_repo.get_by_id = AsyncMock(return_value=tenant)

        # Mock SpiceDB responses
        admin_subjects = [
            SubjectRelation(subject_id="user-admin-1", relation="admin"),
            SubjectRelation(subject_id="user-admin-2", relation="admin"),
        ]
        member_subjects = [
            SubjectRelation(subject_id="user-member-1", relation="member"),
        ]

        async def mock_lookup_subjects(resource, relation, subject_type):
            if relation == "admin":
                return admin_subjects
            elif relation == "member":
                return member_subjects
            return []

        mock_authz.lookup_subjects = AsyncMock(side_effect=mock_lookup_subjects)

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
        mock_authz.lookup_subjects = AsyncMock(return_value=[])

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
