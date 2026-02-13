"""Unit tests for get_authenticated_user dependency.

Tests the tenant-context-free authentication flow that validates JWT tokens
or API keys without requiring X-Tenant-ID header. This is needed for
bootstrap endpoints like list_tenants and create_tenant where the user
doesn't yet have a tenant context.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from iam.application.observability.authentication_probe import AuthenticationProbe
from iam.application.value_objects import AuthenticatedUser
from iam.dependencies.authentication import JWTValidator
from iam.dependencies.user import get_authenticated_user
from iam.domain.value_objects import TenantId, UserId
from shared_kernel.auth import InvalidTokenError
from shared_kernel.auth.jwt_validator import TokenClaims


@pytest.fixture
def mock_jwt_validator() -> MagicMock:
    """Create a mock JWT validator."""
    return MagicMock(spec=JWTValidator)


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


class TestGetAuthenticatedUser:
    """Tests for get_authenticated_user dependency.

    This dependency authenticates via JWT or API key but does NOT resolve
    tenant context. It returns an AuthenticatedUser (without tenant_id).
    """

    @pytest.mark.asyncio
    async def test_returns_authenticated_user_with_valid_jwt(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Should return AuthenticatedUser with user_id and username from JWT claims."""
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await get_authenticated_user(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
        )

        assert isinstance(result, AuthenticatedUser)
        assert result.user_id == UserId(value="external-user-123")
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_does_not_have_tenant_id(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """AuthenticatedUser should NOT have a tenant_id attribute."""
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await get_authenticated_user(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
        )

        assert not hasattr(result, "tenant_id")

    @pytest.mark.asyncio
    async def test_returns_401_for_missing_credentials(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should return 401 when neither JWT token nor API key is provided."""
        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(
                token=None,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer, API-Key"}

    @pytest.mark.asyncio
    async def test_returns_401_for_invalid_token(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
    ) -> None:
        """Should return 401 when JWT token validation fails."""
        mock_jwt_validator.validate_token = AsyncMock(
            side_effect=InvalidTokenError("Invalid token signature")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(
                token=valid_token,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token signature"

    @pytest.mark.asyncio
    async def test_returns_401_for_invalid_api_key(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should return 401 when API key is invalid."""
        mock_api_key_service.validate_and_get_key.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_authenticated_user(
                token=None,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
                x_api_key="invalid-key",
            )

        assert exc_info.value.status_code == 401
        assert "Invalid or expired API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_authenticates_with_valid_api_key(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should return AuthenticatedUser when API key is valid."""
        mock_api_key = MagicMock()
        mock_api_key.id = MagicMock(value="api-key-id-123")
        mock_api_key.created_by_user_id = UserId(value="user-456")
        mock_api_key.tenant_id = TenantId.generate()
        mock_api_key_service.validate_and_get_key.return_value = mock_api_key

        result = await get_authenticated_user(
            token=None,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            x_api_key="valid-api-key",
        )

        assert isinstance(result, AuthenticatedUser)
        assert result.user_id == UserId(value="user-456")

    @pytest.mark.asyncio
    async def test_falls_back_to_sub_when_preferred_username_missing(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
    ) -> None:
        """Should use 'sub' as username when preferred_username is missing."""
        claims = TokenClaims(
            sub="user-123",
            preferred_username=None,
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await get_authenticated_user(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
        )

        assert result.username == "user-123"

    @pytest.mark.asyncio
    async def test_fires_probe_on_successful_jwt_auth(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Should fire authentication probe on successful JWT authentication."""
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        await get_authenticated_user(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
        )

        mock_auth_probe.user_authenticated.assert_called_once_with(
            user_id="external-user-123",
            username="testuser",
        )

    @pytest.mark.asyncio
    async def test_fires_probe_on_failed_auth(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should fire authentication probe on failed authentication."""
        with pytest.raises(HTTPException):
            await get_authenticated_user(
                token=None,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
            )

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Missing authorization"
        )
