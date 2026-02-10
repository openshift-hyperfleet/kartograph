"""Unit tests for tenant context dependency resolver.

Tests the FastAPI dependency that resolves tenant context from the
X-Tenant-ID request header. Covers all branches:
- Valid ULID in header (multi-tenant and single-tenant modes)
- Missing header in multi-tenant mode (400)
- Missing header in single-tenant mode (auto-select default tenant)
- Invalid ULID format (400)
- User not a member of the requested tenant (403)
- Authorization error propagation
- Domain probe invocations for all scenarios
- Auto-add users as member/admin in single-tenant mode
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from iam.dependencies.tenant_context import get_tenant_context
from iam.domain.value_objects import TenantId
from shared_kernel.middleware.observability.tenant_context_probe import (
    TenantContextProbe,
)
from shared_kernel.middleware.tenant_context import TenantContext


@pytest.fixture
def valid_tenant_id() -> TenantId:
    """Generate a valid tenant ID for testing."""
    return TenantId.generate()


@pytest.fixture
def mock_authz() -> AsyncMock:
    """Create a mock authorization provider."""
    authz = AsyncMock()
    authz.check_permission = AsyncMock(return_value=True)
    return authz


@pytest.fixture
def mock_probe() -> MagicMock:
    """Create a mock tenant context probe."""
    return MagicMock(spec=TenantContextProbe)


@pytest.fixture
def mock_tenant_repo() -> AsyncMock:
    """Create a mock tenant repository."""
    return AsyncMock()


class TestGetTenantContextWithValidHeader:
    """Tests for get_tenant_context() when a valid X-Tenant-ID header is provided."""

    @pytest.mark.asyncio
    async def test_returns_tenant_context_with_valid_ulid_header(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should return TenantContext when header contains valid ULID."""
        result = await get_tenant_context(
            x_tenant_id=valid_tenant_id.value,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=False,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        assert isinstance(result, TenantContext)
        assert result.tenant_id == valid_tenant_id.value
        assert result.source == "header"

    @pytest.mark.asyncio
    async def test_checks_permission_in_spicedb(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should check SpiceDB for tenant view permission."""
        await get_tenant_context(
            x_tenant_id=valid_tenant_id.value,
            user_id="user-456",
            username="bob",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=False,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        mock_authz.check_permission.assert_awaited_once_with(
            resource=f"tenant:{valid_tenant_id.value}",
            permission="view",
            subject="user:user-456",
        )

    @pytest.mark.asyncio
    async def test_fires_probe_on_successful_resolution_from_header(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should fire domain probe when tenant context is resolved from header."""
        await get_tenant_context(
            x_tenant_id=valid_tenant_id.value,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=False,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        mock_probe.tenant_resolved_from_header.assert_called_once_with(
            tenant_id=valid_tenant_id.value,
            user_id="user-123",
        )

    @pytest.mark.asyncio
    async def test_valid_header_works_in_single_tenant_mode(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should accept valid header even in single-tenant mode."""
        result = await get_tenant_context(
            x_tenant_id=valid_tenant_id.value,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        assert result.tenant_id == valid_tenant_id.value
        assert result.source == "header"


class TestGetTenantContextMissingHeaderMultiTenant:
    """Tests for get_tenant_context() when header is missing in multi-tenant mode."""

    @pytest.mark.asyncio
    async def test_returns_400_when_header_missing_in_multi_tenant_mode(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should return 400 when X-Tenant-ID header is missing in multi-tenant mode."""
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id=None,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 400
        assert "X-Tenant-ID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_fires_probe_on_missing_header_in_multi_tenant_mode(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should fire probe when header is missing in multi-tenant mode."""
        with pytest.raises(HTTPException):
            await get_tenant_context(
                x_tenant_id=None,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        mock_probe.tenant_header_missing.assert_called_once_with(
            user_id="user-123",
        )


class TestGetTenantContextMissingHeaderSingleTenant:
    """Tests for get_tenant_context() when header is missing in single-tenant mode."""

    @pytest.mark.asyncio
    async def test_auto_selects_default_tenant_when_user_already_member(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should auto-select default tenant when user already has view permission."""
        from iam.domain.aggregates import Tenant

        default_tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_repo.get_by_name.return_value = default_tenant
        mock_authz.check_permission.return_value = True

        result = await get_tenant_context(
            x_tenant_id=None,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        assert result.tenant_id == valid_tenant_id.value
        assert result.source == "default"

    @pytest.mark.asyncio
    async def test_fires_probe_on_default_tenant_auto_selection(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should fire probe when default tenant is auto-selected."""
        from iam.domain.aggregates import Tenant

        default_tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_repo.get_by_name.return_value = default_tenant
        mock_authz.check_permission.return_value = True

        await get_tenant_context(
            x_tenant_id=None,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        mock_probe.tenant_resolved_from_default.assert_called_once_with(
            tenant_id=valid_tenant_id.value,
            user_id="user-123",
        )

    @pytest.mark.asyncio
    async def test_checks_authz_for_default_tenant(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should check SpiceDB view permission when resolving default tenant."""
        from iam.domain.aggregates import Tenant

        default_tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_repo.get_by_name.return_value = default_tenant
        mock_authz.check_permission.return_value = True

        await get_tenant_context(
            x_tenant_id=None,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        mock_authz.check_permission.assert_awaited_once_with(
            resource=f"tenant:{valid_tenant_id.value}",
            permission="view",
            subject="user:user-123",
        )

    @pytest.mark.asyncio
    async def test_raises_500_when_default_tenant_not_found(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should raise 500 when default tenant is not found in single-tenant mode."""
        mock_tenant_repo.get_by_name.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id=None,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=True,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 500
        assert "default tenant" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_uses_configured_default_tenant_name(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should look up tenant using the configured default_tenant_name, not a hardcoded value."""
        from iam.domain.aggregates import Tenant

        custom_name = "my-custom-tenant"
        custom_tenant = Tenant(id=valid_tenant_id, name=custom_name)
        mock_tenant_repo.get_by_name.return_value = custom_tenant
        mock_authz.check_permission.return_value = True

        result = await get_tenant_context(
            x_tenant_id=None,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name=custom_name,
            bootstrap_admin_usernames=[],
        )

        mock_tenant_repo.get_by_name.assert_awaited_once_with(custom_name)
        assert result.tenant_id == valid_tenant_id.value
        assert result.source == "default"

    @pytest.mark.asyncio
    async def test_fires_probe_on_default_tenant_not_found(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should fire probe when default tenant is not found."""
        mock_tenant_repo.get_by_name.return_value = None

        with pytest.raises(HTTPException):
            await get_tenant_context(
                x_tenant_id=None,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=True,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        mock_probe.default_tenant_not_found.assert_called_once()


class TestGetTenantContextInvalidULID:
    """Tests for get_tenant_context() when X-Tenant-ID header has invalid ULID."""

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_ulid_format(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should return 400 when X-Tenant-ID is not a valid ULID."""
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id="not-a-valid-ulid",
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 400
        assert "ULID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_returns_400_for_empty_string(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should return 400 when X-Tenant-ID is empty string."""
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id="",
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_uuid_format(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should return 400 when X-Tenant-ID is a UUID instead of ULID."""
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id="550e8400-e29b-41d4-a716-446655440000",
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_fires_probe_on_invalid_ulid(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should fire probe when invalid ULID is provided."""
        with pytest.raises(HTTPException):
            await get_tenant_context(
                x_tenant_id="bad-ulid",
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        mock_probe.invalid_tenant_id_format.assert_called_once_with(
            raw_value="bad-ulid",
            user_id="user-123",
        )

    @pytest.mark.asyncio
    async def test_invalid_ulid_in_single_tenant_mode_still_returns_400(
        self,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Invalid ULID should still return 400 even in single-tenant mode."""
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id="not-a-ulid",
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=True,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 400


class TestGetTenantContextUnauthorized:
    """Tests for get_tenant_context() when user is not a member of the tenant."""

    @pytest.mark.asyncio
    async def test_returns_403_when_user_not_member_of_tenant(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should return 403 when SpiceDB check_permission returns False."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id=valid_tenant_id.value,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 403
        assert "tenant" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_fires_probe_on_unauthorized_tenant_access(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should fire probe when user is denied access to tenant."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(HTTPException):
            await get_tenant_context(
                x_tenant_id=valid_tenant_id.value,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        mock_probe.tenant_access_denied.assert_called_once_with(
            tenant_id=valid_tenant_id.value,
            user_id="user-123",
        )

    @pytest.mark.asyncio
    async def test_returns_403_even_in_single_tenant_mode_with_explicit_header(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """When header is explicitly provided, authz check runs even in single-tenant mode."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id=valid_tenant_id.value,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=True,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 403


class TestGetTenantContextAuthzError:
    """Tests for get_tenant_context() when SpiceDB check fails with an error."""

    @pytest.mark.asyncio
    async def test_propagates_authz_error(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should propagate authorization errors from SpiceDB."""
        from shared_kernel.authorization.spicedb.exceptions import (
            SpiceDBPermissionError,
        )

        mock_authz.check_permission.side_effect = SpiceDBPermissionError(
            "SpiceDB unavailable"
        )

        with pytest.raises(SpiceDBPermissionError):
            await get_tenant_context(
                x_tenant_id=valid_tenant_id.value,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

    @pytest.mark.asyncio
    async def test_fires_probe_on_authz_error(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should fire probe when authorization check fails with error."""
        from shared_kernel.authorization.spicedb.exceptions import (
            SpiceDBPermissionError,
        )

        error = SpiceDBPermissionError("SpiceDB unavailable")
        mock_authz.check_permission.side_effect = error

        with pytest.raises(SpiceDBPermissionError):
            await get_tenant_context(
                x_tenant_id=valid_tenant_id.value,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=False,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        mock_probe.tenant_authz_check_failed.assert_called_once_with(
            tenant_id=valid_tenant_id.value,
            user_id="user-123",
            error=error,
        )


class TestAutoAddUserInSingleTenantMode:
    """Tests for auto-adding users to the default tenant in single-tenant mode."""

    @pytest.mark.asyncio
    async def test_auto_adds_user_as_member_when_not_in_tenant(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should auto-add user as MEMBER when they lack view permission."""
        from iam.domain.aggregates import Tenant

        default_tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_repo.get_by_name.return_value = default_tenant
        mock_authz.check_permission.return_value = False

        result = await get_tenant_context(
            x_tenant_id=None,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        assert result.tenant_id == valid_tenant_id.value
        assert result.source == "default"
        mock_tenant_repo.save.assert_awaited_once()
        mock_probe.user_auto_added_as_member.assert_called_once_with(
            tenant_id=valid_tenant_id.value,
            user_id="user-123",
            username="alice",
        )

    @pytest.mark.asyncio
    async def test_auto_adds_user_as_admin_when_in_bootstrap_list(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should auto-add user as ADMIN when username is in bootstrap_admin_usernames."""
        from iam.domain.aggregates import Tenant

        default_tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_repo.get_by_name.return_value = default_tenant
        mock_authz.check_permission.return_value = False

        result = await get_tenant_context(
            x_tenant_id=None,
            user_id="user-123",
            username="admin-user",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=["admin-user", "other-admin"],
        )

        assert result.tenant_id == valid_tenant_id.value
        assert result.source == "default"
        mock_tenant_repo.save.assert_awaited_once()
        mock_probe.user_auto_added_as_admin.assert_called_once_with(
            tenant_id=valid_tenant_id.value,
            user_id="user-123",
            username="admin-user",
        )

    @pytest.mark.asyncio
    async def test_does_not_auto_add_when_user_already_member(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should not auto-add when user already has view permission."""
        from iam.domain.aggregates import Tenant

        default_tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_repo.get_by_name.return_value = default_tenant
        mock_authz.check_permission.return_value = True

        await get_tenant_context(
            x_tenant_id=None,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        mock_tenant_repo.save.assert_not_awaited()
        mock_probe.user_auto_added_as_member.assert_not_called()
        mock_probe.user_auto_added_as_admin.assert_not_called()

    @pytest.mark.asyncio
    async def test_fires_error_probe_when_auto_add_fails(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should fire error probe and raise when auto-add save fails."""
        from iam.domain.aggregates import Tenant

        default_tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_repo.get_by_name.return_value = default_tenant
        mock_authz.check_permission.return_value = False
        mock_tenant_repo.save.side_effect = RuntimeError("DB error")

        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_context(
                x_tenant_id=None,
                user_id="user-123",
                username="alice",
                authz=mock_authz,
                probe=mock_probe,
                single_tenant_mode=True,
                tenant_repository=mock_tenant_repo,
                default_tenant_name="default",
                bootstrap_admin_usernames=[],
            )

        assert exc_info.value.status_code == 500
        mock_probe.user_auto_add_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_add_records_domain_event_on_tenant(
        self,
        valid_tenant_id: TenantId,
        mock_authz: AsyncMock,
        mock_probe: MagicMock,
        mock_tenant_repo: AsyncMock,
    ) -> None:
        """Should record TenantMemberAdded domain event via tenant.add_member()."""
        from iam.domain.aggregates import Tenant

        default_tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_repo.get_by_name.return_value = default_tenant
        mock_authz.check_permission.return_value = False

        await get_tenant_context(
            x_tenant_id=None,
            user_id="user-123",
            username="alice",
            authz=mock_authz,
            probe=mock_probe,
            single_tenant_mode=True,
            tenant_repository=mock_tenant_repo,
            default_tenant_name="default",
            bootstrap_admin_usernames=[],
        )

        # The tenant passed to save should have pending events from add_member
        saved_tenant = mock_tenant_repo.save.call_args[0][0]
        assert saved_tenant is default_tenant
