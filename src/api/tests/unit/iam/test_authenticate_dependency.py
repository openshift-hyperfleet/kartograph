"""Unit tests for _authenticate core dependency.

Tests the consolidated authentication logic that validates JWT tokens
or API keys and returns an _AuthResult. This is the single source of
truth for all authentication in the IAM dependency chain.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from iam.application.observability.authentication_probe import AuthenticationProbe
from iam.dependencies.authentication import JWTValidator
from iam.dependencies.user import _authenticate, _AuthResult
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


class TestAuthenticate:
    """Tests for _authenticate — the core authentication dependency.

    This dependency consolidates JWT and API key auth logic, returning
    an _AuthResult with user identity and auth method metadata.
    """

    @pytest.mark.asyncio
    async def test_returns_auth_result_with_valid_jwt(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """Should return _AuthResult with user identity from JWT claims."""
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await _authenticate(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
        )

        assert isinstance(result, _AuthResult)
        assert result.user_id == UserId(value="external-user-123")
        assert result.username == "testuser"
        assert result.is_api_key is False
        assert result.api_key_tenant_id is None

    @pytest.mark.asyncio
    async def test_returns_auth_result_with_valid_api_key(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should return _AuthResult with user identity from API key."""
        tenant_id = TenantId.generate()
        mock_api_key = MagicMock()
        mock_api_key.id = MagicMock(value="api-key-id-123")
        mock_api_key.created_by_user_id = UserId(value="user-456")
        mock_api_key.tenant_id = tenant_id
        mock_api_key_service.validate_and_get_key.return_value = mock_api_key

        result = await _authenticate(
            token=None,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            x_api_key="valid-api-key",
        )

        assert isinstance(result, _AuthResult)
        assert result.user_id == UserId(value="user-456")
        assert result.username == f"api-key:{mock_api_key.id}"
        assert result.is_api_key is True
        assert result.api_key_tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_falls_back_to_sub_when_preferred_username_missing(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
    ) -> None:
        """Should use 'sub' as username when preferred_username is missing."""
        claims = TokenClaims(sub="user-123", preferred_username=None)
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await _authenticate(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
        )

        assert result.username == "user-123"

    @pytest.mark.asyncio
    async def test_raises_401_for_missing_credentials(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should raise 401 when neither JWT token nor API key is provided."""
        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(
                token=None,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer, API-Key"}

    @pytest.mark.asyncio
    async def test_raises_401_for_invalid_jwt(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
    ) -> None:
        """Should raise 401 when JWT token validation fails."""
        mock_jwt_validator.validate_token = AsyncMock(
            side_effect=InvalidTokenError("Invalid token signature")
        )

        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(
                token=valid_token,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token signature"

    @pytest.mark.asyncio
    async def test_raises_401_for_invalid_api_key(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should raise 401 when API key is invalid or expired."""
        mock_api_key_service.validate_and_get_key.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await _authenticate(
                token=None,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
                x_api_key="invalid-key",
            )

        assert exc_info.value.status_code == 401
        assert "Invalid or expired API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_jwt_takes_priority_over_api_key(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
        valid_token_claims: TokenClaims,
    ) -> None:
        """When both JWT and API key are provided, JWT should take priority."""
        mock_jwt_validator.validate_token = AsyncMock(return_value=valid_token_claims)

        result = await _authenticate(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            x_api_key="some-api-key",
        )

        assert result.is_api_key is False
        assert result.user_id == UserId(value="external-user-123")
        mock_api_key_service.validate_and_get_key.assert_not_awaited()

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

        await _authenticate(
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
    async def test_fires_probe_on_successful_api_key_auth(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should fire authentication probe on successful API key authentication."""
        mock_api_key = MagicMock()
        mock_api_key.id = MagicMock(value="api-key-id-123")
        mock_api_key.created_by_user_id = UserId(value="user-456")
        mock_api_key.tenant_id = TenantId.generate()
        mock_api_key_service.validate_and_get_key.return_value = mock_api_key

        await _authenticate(
            token=None,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
            x_api_key="valid-api-key",
        )

        mock_auth_probe.api_key_authentication_succeeded.assert_called_once_with(
            api_key_id="api-key-id-123",
            user_id="user-456",
        )

    @pytest.mark.asyncio
    async def test_fires_probe_on_failed_jwt_auth(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
    ) -> None:
        """Should fire authentication probe on failed JWT authentication."""
        mock_jwt_validator.validate_token = AsyncMock(
            side_effect=InvalidTokenError("Token has expired")
        )

        with pytest.raises(HTTPException):
            await _authenticate(
                token=valid_token,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
            )

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Token has expired"
        )

    @pytest.mark.asyncio
    async def test_fires_probe_on_failed_api_key_auth(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should fire authentication probe on failed API key authentication."""
        mock_api_key_service.validate_and_get_key.return_value = None

        with pytest.raises(HTTPException):
            await _authenticate(
                token=None,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
                x_api_key="invalid-key",
            )

        mock_auth_probe.api_key_authentication_failed.assert_called_once_with(
            reason="invalid_or_expired"
        )

    @pytest.mark.asyncio
    async def test_fires_probe_on_missing_credentials(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
    ) -> None:
        """Should fire authentication probe when no credentials provided."""
        with pytest.raises(HTTPException):
            await _authenticate(
                token=None,
                validator=mock_jwt_validator,
                api_key_service=mock_api_key_service,
                auth_probe=mock_auth_probe,
            )

        mock_auth_probe.authentication_failed.assert_called_once_with(
            reason="Missing authorization"
        )

    @pytest.mark.asyncio
    async def test_handles_non_ulid_user_id_from_external_idp(
        self,
        mock_jwt_validator: MagicMock,
        mock_api_key_service: AsyncMock,
        mock_auth_probe: MagicMock,
        valid_token: str,
    ) -> None:
        """Should accept non-ULID user IDs from external identity providers."""
        claims = TokenClaims(
            sub="auth0|12345678901234567890",
            preferred_username="external-user",
        )
        mock_jwt_validator.validate_token = AsyncMock(return_value=claims)

        result = await _authenticate(
            token=valid_token,
            validator=mock_jwt_validator,
            api_key_service=mock_api_key_service,
            auth_probe=mock_auth_probe,
        )

        assert result.user_id == UserId(value="auth0|12345678901234567890")
        assert result.user_id.value == "auth0|12345678901234567890"
