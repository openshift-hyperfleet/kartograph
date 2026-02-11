"""Unit tests for IAM dependencies.

Tests the JWT Bearer authentication flow in get_current_user.
Tests verify that get_current_user_no_jit uses the tenant context dependency
(get_tenant_context) instead of the walking skeleton's get_default_tenant_id().
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from iam.application.observability.authentication_probe import AuthenticationProbe
from iam.application.value_objects import CurrentUser
from iam.dependencies.authentication import JWTValidator
from iam.dependencies.user import get_current_user, get_current_user_no_jit
from iam.domain.value_objects import TenantId, UserId
from shared_kernel.auth import InvalidTokenError
from shared_kernel.auth.jwt_validator import TokenClaims
from shared_kernel.middleware.observability.tenant_context_probe import (
    TenantContextProbe,
)
from shared_kernel.middleware.tenant_context import TenantContext


@pytest.fixture
def mock_jwt_validator() -> MagicMock:
    """Create a mock JWT validator."""
    return MagicMock(spec=JWTValidator)


@pytest.fixture
def mock_user_service() -> AsyncMock:
    """Create a mock user service."""
    service = AsyncMock()
    service.ensure_user = AsyncMock()
    return service


@pytest.fixture
def mock_auth_probe() -> MagicMock:
    """Create a mock authentication probe."""
    return MagicMock(spec=AuthenticationProbe)


@pytest.fixture
def mock_api_key_service() -> AsyncMock:
    """Create a mock API key service."""
    service = AsyncMock()
    service.validate_and_get_key = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_tenant_context_probe() -> MagicMock:
    """Create a mock tenant context probe."""
    return MagicMock(spec=TenantContextProbe)


@pytest.fixture
def mock_authz() -> AsyncMock:
    """Create a mock authorization provider."""
    authz = AsyncMock()
    authz.check_permission = AsyncMock(return_value=True)
    return authz


@pytest.fixture
def mock_tenant_repo() -> AsyncMock:
    """Create a mock tenant repository."""
    return AsyncMock()


@pytest.fixture
def tenant_id() -> TenantId:
    """Generate a tenant ID for tests (no walking skeleton global state)."""
    return TenantId.generate()


@pytest.fixture
def tenant_context(tenant_id: TenantId) -> TenantContext:
    """Create a TenantContext for tests, simulating resolved tenant context."""
    return TenantContext(tenant_id=tenant_id.value, source="default")


@pytest.fixture
def valid_token() -> str:
    """Create valid Bearer token string."""
    return "valid.jwt.token"


@pytest.fixture
def valid_token_claims() -> TokenClaims:
    """Create valid token claims."""
    return TokenClaims(
        sub="external-user-123",
        preferred_username="testuser",
    )


class TestGetCurrentUserNoJit:
    """Tests for get_current_user_no_jit dependency (authentication without JIT provisioning).

    Verifies that get_current_user_no_jit resolves tenant context via get_tenant_context
    instead of the walking skeleton's get_default_tenant_id().
    """

    @pytest.mark.asyncio
    async def test_successful_authentication_with_valid_jwt(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Test successful authentication with a valid JWT token.

        The tenant context should come from get_tenant_context, not from
        a hardcoded walking skeleton global.
        """
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await get_current_user_no_jit(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            tenant_context=tenant_context,
        )

        assert isinstance(result, CurrentUser)
        assert result.user_id == UserId(value="external-user-123")
        assert result.username == "testuser"
        assert result.tenant_id == TenantId(value=tenant_context.tenant_id)

        mock_jwt_validator.validate_token.assert_awaited_once_with("valid.jwt.token")
        mock_auth_probe.user_authenticated.assert_called_once_with(
            user_id="external-user-123",
            username="testuser",
        )

    @pytest.mark.asyncio
    async def test_returns_401_for_missing_authorization_header(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
    ) -> None:
        """Test 401 response when Authorization header is missing."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_no_jit(
                token=None,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
                tenant_context=tenant_context,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer, API-Key"}

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Missing authorization"
        )

    @pytest.mark.asyncio
    async def test_returns_401_for_invalid_token(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
        valid_token: str,
    ) -> None:
        """Test 401 response when token validation fails."""
        mock_jwt_validator.validate_token = AsyncMock(
            side_effect=InvalidTokenError("Invalid token signature")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_no_jit(
                token=valid_token,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
                tenant_context=tenant_context,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token signature"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer, API-Key"}

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Invalid token signature"
        )

    @pytest.mark.asyncio
    async def test_returns_401_for_expired_token(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
        valid_token: str,
    ) -> None:
        """Test 401 response when token has expired."""
        mock_jwt_validator.validate_token = AsyncMock(
            side_effect=InvalidTokenError("Token has expired")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_no_jit(
                token=valid_token,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
                tenant_context=tenant_context,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token has expired"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer, API-Key"}

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Token has expired"
        )

    @pytest.mark.asyncio
    async def test_extracts_user_id_from_sub_claim(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
        valid_token: str,
    ) -> None:
        """Test that user_id is correctly extracted from 'sub' claim."""
        claims = TokenClaims(
            sub="keycloak-user-uuid-12345",
            preferred_username="john.doe",
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_current_user_no_jit(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            tenant_context=tenant_context,
        )

        assert result.user_id == UserId(value="keycloak-user-uuid-12345")

    @pytest.mark.asyncio
    async def test_extracts_username_from_preferred_username_claim(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
        valid_token: str,
    ) -> None:
        """Test that username is extracted from 'preferred_username' claim."""
        claims = TokenClaims(
            sub="user-123",
            preferred_username="jane.smith",
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_current_user_no_jit(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            tenant_context=tenant_context,
        )

        assert result.username == "jane.smith"

    @pytest.mark.asyncio
    async def test_falls_back_to_sub_when_preferred_username_missing(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
        valid_token: str,
    ) -> None:
        """Test that username falls back to 'sub' when preferred_username is missing."""
        claims = TokenClaims(
            sub="user-123",
            preferred_username=None,
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_current_user_no_jit(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            tenant_context=tenant_context,
        )

        assert result.username == "user-123"

    @pytest.mark.asyncio
    async def test_uses_tenant_context_for_tenant_resolution(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Test that tenant ID comes from the TenantContext dependency, not walking skeleton.

        This is the key behavioral change: the tenant is resolved via
        get_tenant_context (which handles headers, SpiceDB checks, and
        single-tenant mode auto-selection) rather than from a cached global.
        """
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await get_current_user_no_jit(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            tenant_context=tenant_context,
        )

        assert result.tenant_id == TenantId(value=tenant_context.tenant_id)

    @pytest.mark.asyncio
    async def test_tenant_context_with_header_source(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Test that tenant context from explicit header works correctly."""
        header_tenant_id = TenantId.generate()
        header_context = TenantContext(
            tenant_id=header_tenant_id.value, source="header"
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await get_current_user_no_jit(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            tenant_context=header_context,
        )

        assert result.tenant_id == header_tenant_id

    @pytest.mark.asyncio
    async def test_handles_non_ulid_user_id_from_external_idp(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        tenant_context: TenantContext,
        valid_token: str,
    ) -> None:
        """Test that non-ULID user IDs from external IdP are accepted."""
        claims = TokenClaims(
            sub="auth0|12345678901234567890",
            preferred_username="external-user",
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_current_user_no_jit(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            tenant_context=tenant_context,
        )

        assert result.user_id == UserId(value="auth0|12345678901234567890")
        assert result.user_id.value == "auth0|12345678901234567890"


class TestGetCurrentUser:
    """Tests for get_current_user dependency (with JIT user provisioning)."""

    @pytest.mark.asyncio
    async def test_calls_jit_user_provisioning_for_bearer_token(
        self,
        mock_user_service: AsyncMock,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Test that JIT user provisioning is called for Bearer token authentication."""
        current_user = CurrentUser(
            user_id=UserId(value=valid_token_claims.sub),
            username=valid_token_claims.preferred_username or valid_token_claims.sub,
            tenant_id=TenantId.generate(),
        )

        result = await get_current_user(
            current_user=current_user,
            user_service=mock_user_service,
            token="some.bearer.token",  # Simulating a Bearer token
        )

        # Should call ensure_user for JIT provisioning
        mock_user_service.ensure_user.assert_awaited_once_with(
            user_id=current_user.user_id,
            username=current_user.username,
        )
        assert result == current_user

    @pytest.mark.asyncio
    async def test_skips_jit_provisioning_for_api_key(
        self,
        mock_user_service: AsyncMock,
    ) -> None:
        """Test that JIT user provisioning is skipped for API key authentication."""
        current_user = CurrentUser(
            user_id=UserId.generate(),
            username="api-key:my-key",
            tenant_id=TenantId.generate(),
        )

        result = await get_current_user(
            current_user=current_user,
            user_service=mock_user_service,
            token=None,  # No Bearer token means API key auth
        )

        # Should NOT call ensure_user for API keys
        mock_user_service.ensure_user.assert_not_awaited()
        assert result == current_user
