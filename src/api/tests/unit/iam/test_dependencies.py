"""Unit tests for IAM dependencies.

Tests the composition of get_current_user_no_jit and get_current_user
over _authenticate and resolve_tenant_context.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from iam.application.observability import UserServiceProbe
from iam.application.value_objects import CurrentUser
from iam.dependencies.user import (
    _AuthResult,
    get_current_user,
    get_current_user_no_jit,
)
from iam.domain.value_objects import TenantId, UserId
from shared_kernel.middleware.tenant_context import TenantContext


@pytest.fixture
def tenant_id() -> TenantId:
    """Generate a tenant ID for tests."""
    return TenantId.generate()


@pytest.fixture
def tenant_context(tenant_id: TenantId) -> TenantContext:
    """Create a TenantContext for tests, simulating resolved tenant context."""
    return TenantContext(tenant_id=tenant_id.value, source="default")


@pytest.fixture
def jwt_auth_result() -> _AuthResult:
    """Create an _AuthResult for JWT-authenticated user."""
    return _AuthResult(
        user_id=UserId(value="external-user-123"),
        username="testuser",
        api_key_tenant_id=None,
        is_api_key=False,
    )


@pytest.fixture
def api_key_tenant_id() -> TenantId:
    """Generate a tenant ID for API key auth."""
    return TenantId.generate()


@pytest.fixture
def api_key_auth_result(api_key_tenant_id: TenantId) -> _AuthResult:
    """Create an _AuthResult for API-key-authenticated user."""
    return _AuthResult(
        user_id=UserId(value="user-456"),
        username="api-key:api-key-id-123",
        api_key_tenant_id=api_key_tenant_id,
        is_api_key=True,
    )


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Create a mock user repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session with begin() context manager."""
    session = AsyncMock()
    session.begin = MagicMock(return_value=AsyncMock())
    return session


@pytest.fixture
def mock_probe() -> MagicMock:
    """Create a mock user service probe."""
    return MagicMock(spec=UserServiceProbe)


class TestGetCurrentUserNoJit:
    """Tests for get_current_user_no_jit dependency.

    This dependency composes _authenticate with resolve_tenant_context
    to produce a CurrentUser with tenant scoping, without JIT provisioning.
    """

    @pytest.mark.asyncio
    async def test_returns_current_user_with_jwt_auth(
        self,
        jwt_auth_result: _AuthResult,
        tenant_context: TenantContext,
    ) -> None:
        """Should return CurrentUser with tenant_id from tenant context."""
        result = await get_current_user_no_jit(
            auth_result=jwt_auth_result,
            tenant_context=tenant_context,
        )

        assert isinstance(result, CurrentUser)
        assert result.user_id == UserId(value="external-user-123")
        assert result.username == "testuser"
        assert result.tenant_id == TenantId(value=tenant_context.tenant_id)

    @pytest.mark.asyncio
    async def test_uses_api_key_tenant_id_for_api_key_auth(
        self,
        api_key_auth_result: _AuthResult,
        api_key_tenant_id: TenantId,
        tenant_context: TenantContext,
    ) -> None:
        """Should use tenant_id from API key, not from tenant context."""
        result = await get_current_user_no_jit(
            auth_result=api_key_auth_result,
            tenant_context=tenant_context,
        )

        assert result.tenant_id == api_key_tenant_id
        assert result.user_id == UserId(value="user-456")

    @pytest.mark.asyncio
    async def test_tenant_context_with_header_source(
        self,
        jwt_auth_result: _AuthResult,
    ) -> None:
        """Should use tenant context from explicit header."""
        header_tenant_id = TenantId.generate()
        header_context = TenantContext(
            tenant_id=header_tenant_id.value, source="header"
        )

        result = await get_current_user_no_jit(
            auth_result=jwt_auth_result,
            tenant_context=header_context,
        )

        assert result.tenant_id == header_tenant_id

    @pytest.mark.asyncio
    async def test_handles_non_ulid_user_id_from_external_idp(
        self,
        tenant_context: TenantContext,
    ) -> None:
        """Should accept non-ULID user IDs from external identity providers."""
        auth_result = _AuthResult(
            user_id=UserId(value="auth0|12345678901234567890"),
            username="external-user",
            api_key_tenant_id=None,
            is_api_key=False,
        )

        result = await get_current_user_no_jit(
            auth_result=auth_result,
            tenant_context=tenant_context,
        )

        assert result.user_id == UserId(value="auth0|12345678901234567890")
        assert result.user_id.value == "auth0|12345678901234567890"


class TestGetCurrentUser:
    """Tests for get_current_user dependency (with JIT user provisioning)."""

    @pytest.mark.asyncio
    async def test_calls_jit_user_provisioning_for_bearer_token(
        self,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """Should JIT provision user for Bearer token authentication."""
        current_user = CurrentUser(
            user_id=UserId(value="external-user-123"),
            username="testuser",
            tenant_id=TenantId.generate(),
        )

        result = await get_current_user(
            current_user=current_user,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
            token="some.bearer.token",
        )

        mock_user_repo.get_by_id.assert_awaited_once()
        assert result == current_user

    @pytest.mark.asyncio
    async def test_skips_jit_provisioning_for_api_key(
        self,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """Should NOT JIT provision for API key authentication."""
        current_user = CurrentUser(
            user_id=UserId.generate(),
            username="api-key:my-key",
            tenant_id=TenantId.generate(),
        )

        result = await get_current_user(
            current_user=current_user,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
            token=None,
        )

        mock_user_repo.get_by_id.assert_not_awaited()
        mock_user_repo.save.assert_not_awaited()
        assert result == current_user
