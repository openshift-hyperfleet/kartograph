"""Unit tests for IAM dependencies.

Tests the JWT Bearer authentication flow in get_current_user.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from iam.application.observability import AuthenticationProbe
from iam.application.value_objects import CurrentUser
from iam.dependencies import (
    get_current_user,
    get_default_tenant_id,
    set_default_tenant_id,
)
from iam.domain.value_objects import TenantId, UserId
from shared_kernel.auth import InvalidTokenError, JWTValidator, TokenClaims


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
def default_tenant_id() -> TenantId:
    """Set up default tenant for tests."""
    tenant_id = TenantId.generate()
    set_default_tenant_id(tenant_id)
    return tenant_id


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
        raw_claims={
            "sub": "external-user-123",
            "preferred_username": "testuser",
            "iss": "https://auth.example.com/realms/test",
            "aud": "kartograph-api",
        },
    )


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_successful_authentication_with_valid_jwt(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Test successful authentication with a valid JWT token."""
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await get_current_user(
            token=valid_token,
            validator=mock_jwt_validator,
            user_service=mock_user_service,
            auth_probe=mock_auth_probe,
        )

        assert isinstance(result, CurrentUser)
        assert result.user_id == UserId(value="external-user-123")
        assert result.username == "testuser"
        assert result.tenant_id == default_tenant_id

        mock_jwt_validator.validate_token.assert_awaited_once_with("valid.jwt.token")
        mock_user_service.ensure_user.assert_awaited_once()
        mock_auth_probe.user_authenticated.assert_called_once_with(
            user_id="external-user-123",
            username="testuser",
        )

    @pytest.mark.asyncio
    async def test_returns_401_for_missing_authorization_header(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
    ) -> None:
        """Test 401 response when Authorization header is missing."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=None,
                validator=mock_jwt_validator,
                user_service=mock_user_service,
                auth_probe=mock_auth_probe,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Missing authorization header"
        )

    @pytest.mark.asyncio
    async def test_returns_401_for_invalid_token(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
    ) -> None:
        """Test 401 response when token validation fails."""
        mock_jwt_validator.validate_token = AsyncMock(
            side_effect=InvalidTokenError("Invalid token signature")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=valid_token,
                validator=mock_jwt_validator,
                user_service=mock_user_service,
                auth_probe=mock_auth_probe,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token signature"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Invalid token signature"
        )

    @pytest.mark.asyncio
    async def test_returns_401_for_expired_token(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
    ) -> None:
        """Test 401 response when token has expired."""
        mock_jwt_validator.validate_token = AsyncMock(
            side_effect=InvalidTokenError("Token has expired")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=valid_token,
                validator=mock_jwt_validator,
                user_service=mock_user_service,
                auth_probe=mock_auth_probe,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token has expired"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Token has expired"
        )

    @pytest.mark.asyncio
    async def test_extracts_user_id_from_sub_claim(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
    ) -> None:
        """Test that user_id is correctly extracted from 'sub' claim."""
        claims = TokenClaims(
            sub="keycloak-user-uuid-12345",
            preferred_username="john.doe",
            raw_claims={"sub": "keycloak-user-uuid-12345"},
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_current_user(
            token=valid_token,
            validator=mock_jwt_validator,
            user_service=mock_user_service,
            auth_probe=mock_auth_probe,
        )

        assert result.user_id == UserId(value="keycloak-user-uuid-12345")

    @pytest.mark.asyncio
    async def test_extracts_username_from_preferred_username_claim(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
    ) -> None:
        """Test that username is extracted from 'preferred_username' claim."""
        claims = TokenClaims(
            sub="user-123",
            preferred_username="jane.smith",
            raw_claims={"sub": "user-123", "preferred_username": "jane.smith"},
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_current_user(
            token=valid_token,
            validator=mock_jwt_validator,
            user_service=mock_user_service,
            auth_probe=mock_auth_probe,
        )

        assert result.username == "jane.smith"

    @pytest.mark.asyncio
    async def test_falls_back_to_sub_when_preferred_username_missing(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
    ) -> None:
        """Test that username falls back to 'sub' when preferred_username is missing."""
        claims = TokenClaims(
            sub="user-123",
            preferred_username=None,
            raw_claims={"sub": "user-123"},
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_current_user(
            token=valid_token,
            validator=mock_jwt_validator,
            user_service=mock_user_service,
            auth_probe=mock_auth_probe,
        )

        assert result.username == "user-123"

    @pytest.mark.asyncio
    async def test_calls_jit_user_provisioning(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Test that JIT user provisioning is called with correct parameters."""
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        await get_current_user(
            token=valid_token,
            validator=mock_jwt_validator,
            user_service=mock_user_service,
            auth_probe=mock_auth_probe,
        )

        mock_user_service.ensure_user.assert_awaited_once_with(
            user_id=UserId(value="external-user-123"),
            username="testuser",
        )

    @pytest.mark.asyncio
    async def test_uses_default_tenant_for_single_tenant_mode(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Test that default tenant is used in single-tenant mode."""
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await get_current_user(
            token=valid_token,
            validator=mock_jwt_validator,
            user_service=mock_user_service,
            auth_probe=mock_auth_probe,
        )

        assert result.tenant_id == default_tenant_id
        assert result.tenant_id == get_default_tenant_id()

    @pytest.mark.asyncio
    async def test_handles_non_ulid_user_id_from_external_idp(
        self,
        mock_jwt_validator: MagicMock,
        mock_user_service: AsyncMock,
        mock_auth_probe: MagicMock,
        default_tenant_id: TenantId,
        valid_token: str,
    ) -> None:
        """Test that non-ULID user IDs from external IdP are accepted."""
        claims = TokenClaims(
            sub="auth0|12345678901234567890",
            preferred_username="external-user",
            raw_claims={"sub": "auth0|12345678901234567890"},
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_current_user(
            token=valid_token,
            validator=mock_jwt_validator,
            user_service=mock_user_service,
            auth_probe=mock_auth_probe,
        )

        assert result.user_id == UserId(value="auth0|12345678901234567890")
        assert result.user_id.value == "auth0|12345678901234567890"
