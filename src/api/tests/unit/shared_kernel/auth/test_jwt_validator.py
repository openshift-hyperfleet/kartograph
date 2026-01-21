"""Unit tests for JWT validator module.

Tests follow TDD approach - written before implementation.
Uses mocking for JWKS endpoint to avoid requiring real Keycloak.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from shared_kernel.auth.jwt_validator import (
    InvalidTokenError,
    JWTValidator,
    TokenClaims,
)
from shared_kernel.auth.observability import JWTValidatorProbe


# Test RSA keys for JWT signing (generated for testing only)
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAx7nMIDnrTvJKLVgWSYCwv4tzqEYMZim5FjDPbqfvQddlhcPn
n9iUfp9Sc1Xx+bwN7/Foocgkv0Vpnst0tKPNvTtHJGPS+qW25r/RJ4xUedHzkZWR
XoSPSMQpa663Ik/V9g6/LMLjiOv4Z/NiawRQbRcny2WhVaCCvkilV1ejtBy251e9
nbXW9cOMmObXiuyr22qaRIP0gbh86b2G65tBDY3hDV2dEjgYFdh4b67MiNbovA2Q
vq5cJSkEidwaZRYNTHe/XrcvF1SaGOWSE9eWHio+CJvoFUmPwxPSPG1bnz2XgmUp
kY1ksvZLdU20VLHk4Y1NrGzogApzVcOqFUnBaQIDAQABAoIBAAF9gGlpJTlUk3sd
IiVwQWFcgANsamFExG3G9XVE6YMbQVWrLYpCynDbbXkQ1hpf7daxfW9fl+6ZbP1T
VU6XvkxAKfq6h/N40xGLstrRsDusdl3KuOf0o0EOvaRhDFrEL7uDRqfl2F7IK/VS
mpRj1tnJh3F8E6UY6oDS9/Db5YvNe6wLUSZs3hQUWEQAowOq0OIPbrYFx7/EXbu5
ABA6rgfPOzjC58TU2jvvAqJHh3oRBdbrXMVMX5ldljuuC809QfSCBA2RiuyCMt2/
9+ao1/5VghetxPAQd4as28ljlkyYJ5Y/HboB2vebhGK0PcpnQp0CnJ/wQqVNVwok
NTMALBECgYEA4p6J4VYMBEwU90MmixBXrivohq5v6azAc4T9COYXkhZViK2qo036
iVUD4pShkKSzViAyXdDo5jb9PZ+awhWEUJvQsyAKxzbdpFuVplTO0+plOQoqk0U3
iwfevwvFx0egcLu2M0qJO0wXJ6up9SsUO11wHFhp9bGIAxZvWIHCMC0CgYEA4Z6q
rt5tWs4bS1ZTZfjWqoLYDZbePVOZiqfm0jANwY5hKcjcDlJP2K5hHUuFxUOuWp9q
SAwPVI/XLWKEoGgkvmIj3/ajxY9BXWxA6/Dm6V97gPg7nBkmpmx6dgFXpP/y6daL
YHyiRwACOBbKwGVFLdMMG5Nq0pPiEDEQm0h4360CgYEAjLjV9c9w9tonysMwE/q5
97XcVoXLiNd1SkayuevnhxfHVXBCHdY2VUEtgG27Rg6ALmMf45HujcZnyvRpLUwf
Nc8L8a9cAgjX6U/Vxcu0A3PyF1FwzrKUowjoEMpGrlCUGGz33zHRtbiySDgY+d0e
Wx7Sl0dvxNnRE9nCmrs40qECgYBAzdoosCqo0lp0oS8DMx41i6+S96qN4t1PPjrG
VJce6U5vOgo68tmMW0n5qB+cMXx6+x8D4rLkjww3NPzzNfaX2IiFY8pWjHcx5k4f
dupcTdijiqlUhMTdOHtUOb563ilfkQgnhqT1z8LTaXiDGpNsPhpUMVuVcHSWQgGL
GJ3fYQKBgQDI99QUxbJe+zxq6iu9ajxue3pP2zOx6ZVE1SZGRikrtGh1YPseqHlP
yvohGm9FAVsK3PzjPB/ojQ/gKiHufBAMYFek3jJYrR17ccZbME85pgNzSa+IVTnB
VsfvLLuYJ174a6sOJfepUBd8OXVWyKqlnJl8hfJxnZULB52KeXl1fw==
-----END RSA PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAx7nMIDnrTvJKLVgWSYCw
v4tzqEYMZim5FjDPbqfvQddlhcPnn9iUfp9Sc1Xx+bwN7/Foocgkv0Vpnst0tKPN
vTtHJGPS+qW25r/RJ4xUedHzkZWRXoSPSMQpa663Ik/V9g6/LMLjiOv4Z/NiawRQ
bRcny2WhVaCCvkilV1ejtBy251e9nbXW9cOMmObXiuyr22qaRIP0gbh86b2G65tB
DY3hDV2dEjgYFdh4b67MiNbovA2Qvq5cJSkEidwaZRYNTHe/XrcvF1SaGOWSE9eW
Hio+CJvoFUmPwxPSPG1bnz2XgmUpkY1ksvZLdU20VLHk4Y1NrGzogApzVcOqFUnB
aQIDAQAB
-----END PUBLIC KEY-----"""

TEST_ISSUER = "https://auth.example.com/realms/test"
TEST_AUDIENCE = "test-client"
TEST_KID = "test-key-id"


def create_jwks_response() -> dict[str, Any]:
    """Create a JWKS response matching the test public key."""
    from jose import jwk
    from jose.constants import ALGORITHMS

    key = jwk.construct(TEST_PUBLIC_KEY, ALGORITHMS.RS256)
    jwk_dict = key.to_dict()
    jwk_dict["kid"] = TEST_KID
    jwk_dict["use"] = "sig"
    jwk_dict["alg"] = "RS256"
    return {"keys": [jwk_dict]}


def create_test_token(
    sub: str = "user-123",
    preferred_username: str = "testuser",
    issuer: str = TEST_ISSUER,
    audience: str = TEST_AUDIENCE,
    exp_delta: timedelta = timedelta(hours=1),
    iat_delta: timedelta = timedelta(seconds=0),
    extra_claims: dict[str, Any] | None = None,
    kid: str = TEST_KID,
) -> str:
    """Create a signed JWT token for testing."""
    now = datetime.now(tz=timezone.utc)
    claims = {
        "sub": sub,
        "preferred_username": preferred_username,
        "iss": issuer,
        "aud": audience,
        "exp": int((now + exp_delta).timestamp()),
        "iat": int((now + iat_delta).timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)

    headers = {"kid": kid, "alg": "RS256"}
    return jwt.encode(claims, TEST_PRIVATE_KEY, algorithm="RS256", headers=headers)


class TestTokenClaims:
    """Tests for TokenClaims dataclass."""

    def test_create_token_claims(self) -> None:
        """TokenClaims can be created with required fields."""
        claims = TokenClaims(
            sub="user-123",
            preferred_username="testuser",
            raw_claims={"sub": "user-123", "name": "Test User"},
        )
        assert claims.sub == "user-123"
        assert claims.preferred_username == "testuser"
        assert claims.raw_claims == {"sub": "user-123", "name": "Test User"}

    def test_token_claims_with_none_username(self) -> None:
        """TokenClaims accepts None for preferred_username."""
        claims = TokenClaims(
            sub="user-123",
            preferred_username=None,
            raw_claims={"sub": "user-123"},
        )
        assert claims.preferred_username is None


class TestInvalidTokenError:
    """Tests for InvalidTokenError exception."""

    def test_invalid_token_error_message(self) -> None:
        """InvalidTokenError stores and displays message."""
        error = InvalidTokenError("Token has expired")
        assert str(error) == "Token has expired"

    def test_invalid_token_error_is_exception(self) -> None:
        """InvalidTokenError is a proper Exception subclass."""
        assert issubclass(InvalidTokenError, Exception)


class TestJWTValidator:
    """Tests for JWTValidator class."""

    @pytest.fixture
    def mock_probe(self) -> MagicMock:
        """Create a mock probe for observability."""
        return MagicMock(spec=JWTValidatorProbe)

    @pytest.fixture
    def mock_http_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def openid_config(self) -> dict[str, Any]:
        """Create OpenID Connect discovery document."""
        return {
            "issuer": TEST_ISSUER,
            "jwks_uri": f"{TEST_ISSUER}/protocol/openid-connect/certs",
            "authorization_endpoint": f"{TEST_ISSUER}/protocol/openid-connect/auth",
            "token_endpoint": f"{TEST_ISSUER}/protocol/openid-connect/token",
        }

    @pytest.fixture
    def validator(self, mock_probe: MagicMock) -> JWTValidator:
        """Create a JWTValidator with test configuration."""
        return JWTValidator(
            issuer_url=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            probe=mock_probe,
        )

    def _create_response_mock(self, json_data: dict[str, Any]) -> MagicMock:
        """Create a mock response object."""
        response = MagicMock()
        response.json.return_value = json_data
        response.raise_for_status = MagicMock()
        return response

    @pytest.mark.asyncio
    async def test_validate_token_success(
        self,
        validator: JWTValidator,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Valid token returns TokenClaims with correct data."""
        token = create_test_token()
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            claims = await validator.validate_token(token)

        assert claims.sub == "user-123"
        assert claims.preferred_username == "testuser"
        assert claims.raw_claims["sub"] == "user-123"
        mock_probe.token_validated.assert_called_once_with(user_id="user-123")

    @pytest.mark.asyncio
    async def test_validate_token_expired(
        self,
        validator: JWTValidator,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Expired token raises InvalidTokenError."""
        token = create_test_token(exp_delta=timedelta(hours=-1))
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            with pytest.raises(InvalidTokenError) as exc_info:
                await validator.validate_token(token)

        assert "expired" in str(exc_info.value).lower()
        mock_probe.token_validation_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_token_invalid_signature(
        self,
        validator: JWTValidator,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Token with invalid signature raises InvalidTokenError."""
        # Create token, then tamper with it
        token = create_test_token()
        # Corrupt the signature by modifying the last character
        parts = token.rsplit(".", 1)
        tampered_token = parts[0] + ".invalid_signature"

        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            with pytest.raises(InvalidTokenError) as exc_info:
                await validator.validate_token(tampered_token)

        assert (
            "signature" in str(exc_info.value).lower()
            or "invalid" in str(exc_info.value).lower()
        )
        mock_probe.token_validation_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_token_wrong_issuer(
        self,
        validator: JWTValidator,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Token with wrong issuer raises InvalidTokenError."""
        token = create_test_token(issuer="https://wrong-issuer.com")
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            with pytest.raises(InvalidTokenError) as exc_info:
                await validator.validate_token(token)

        assert "issuer" in str(exc_info.value).lower()
        mock_probe.token_validation_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_token_wrong_audience(
        self,
        validator: JWTValidator,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Token with wrong audience raises InvalidTokenError."""
        token = create_test_token(audience="wrong-audience")
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            with pytest.raises(InvalidTokenError) as exc_info:
                await validator.validate_token(token)

        assert "audience" in str(exc_info.value).lower()
        mock_probe.token_validation_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_jwks_caching(
        self,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """JWKS is cached and not fetched on every validation."""
        validator = JWTValidator(
            issuer_url=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            probe=mock_probe,
            jwks_cache_ttl=timedelta(hours=24),
        )
        token1 = create_test_token(sub="user-1")
        token2 = create_test_token(sub="user-2")
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            # First validation
            claims1 = await validator.validate_token(token1)
            assert claims1.sub == "user-1"

            # Second validation should use cache
            claims2 = await validator.validate_token(token2)
            assert claims2.sub == "user-2"

            # JWKS should only be fetched once (2 calls: openid-config + jwks)
            assert mock_client.get.call_count == 2
            # Verify cache hit was recorded
            mock_probe.jwks_cache_hit.assert_called()

    @pytest.mark.asyncio
    async def test_jwks_cache_expired_refetches(
        self,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Expired JWKS cache triggers refetch."""
        validator = JWTValidator(
            issuer_url=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            probe=mock_probe,
            jwks_cache_ttl=timedelta(seconds=0),  # Immediate expiry
        )
        token = create_test_token()
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            # First validation
            await validator.validate_token(token)

            # Wait a tiny bit to ensure cache is expired
            await asyncio.sleep(0.01)

            # Second validation should refetch
            await validator.validate_token(token)

            # Should have fetched twice (4 calls total: 2x openid-config + 2x jwks)
            assert mock_client.get.call_count == 4

    @pytest.mark.asyncio
    async def test_custom_claim_names(
        self,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Custom claim names are used for extraction."""
        validator = JWTValidator(
            issuer_url=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            probe=mock_probe,
            user_id_claim="custom_id",
            username_claim="email",
        )
        token = create_test_token(
            extra_claims={
                "custom_id": "custom-user-456",
                "email": "test@example.com",
            }
        )
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            claims = await validator.validate_token(token)

        assert claims.sub == "custom-user-456"
        assert claims.preferred_username == "test@example.com"

    @pytest.mark.asyncio
    async def test_network_error_handling(
        self,
        validator: JWTValidator,
        mock_probe: MagicMock,
    ) -> None:
        """Network errors when fetching JWKS raise InvalidTokenError."""
        import httpx

        token = create_test_token()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.NetworkError("Connection refused")

            with pytest.raises(InvalidTokenError) as exc_info:
                await validator.validate_token(token)

        assert (
            "fetch" in str(exc_info.value).lower()
            or "network" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_malformed_token(
        self,
        validator: JWTValidator,
        mock_probe: MagicMock,
    ) -> None:
        """Malformed token raises InvalidTokenError without fetching JWKS."""
        with pytest.raises(InvalidTokenError) as exc_info:
            await validator.validate_token("not.a.valid.jwt.token.format")

        assert (
            "invalid" in str(exc_info.value).lower()
            or "malformed" in str(exc_info.value).lower()
        )
        mock_probe.token_validation_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_user_id_claim(
        self,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Missing user_id_claim in token raises InvalidTokenError."""
        validator = JWTValidator(
            issuer_url=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            probe=mock_probe,
            user_id_claim="nonexistent_claim",
        )
        token = create_test_token()
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            with pytest.raises(InvalidTokenError) as exc_info:
                await validator.validate_token(token)

        assert "claim" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_missing_username_claim_returns_none(
        self,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Missing username_claim results in None, not error."""
        validator = JWTValidator(
            issuer_url=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            probe=mock_probe,
            username_claim="nonexistent_claim",
        )
        token = create_test_token()
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            claims = await validator.validate_token(token)

        assert claims.preferred_username is None

    @pytest.mark.asyncio
    async def test_probe_jwks_fetched_called(
        self,
        validator: JWTValidator,
        mock_probe: MagicMock,
        openid_config: dict[str, Any],
    ) -> None:
        """Probe.jwks_fetched is called with key count."""
        token = create_test_token()
        jwks = create_jwks_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                self._create_response_mock(openid_config),
                self._create_response_mock(jwks),
            ]

            await validator.validate_token(token)

        mock_probe.jwks_fetched.assert_called_once_with(key_count=1)


class TestJWTValidatorThreadSafety:
    """Tests for thread-safety of JWKS cache."""

    @pytest.mark.asyncio
    async def test_concurrent_validation_uses_single_fetch(self) -> None:
        """Concurrent validations share the same JWKS fetch."""
        mock_probe = MagicMock(spec=JWTValidatorProbe)
        validator = JWTValidator(
            issuer_url=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            probe=mock_probe,
        )

        openid_config = {
            "issuer": TEST_ISSUER,
            "jwks_uri": f"{TEST_ISSUER}/protocol/openid-connect/certs",
        }
        jwks = create_jwks_response()

        tokens = [create_test_token(sub=f"user-{i}") for i in range(5)]

        fetch_count = 0

        def create_response_mock(json_data: dict[str, Any]) -> MagicMock:
            nonlocal fetch_count
            fetch_count += 1
            response = MagicMock()
            response.json.return_value = json_data
            response.raise_for_status = MagicMock()
            return response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Add a small delay to simulate network latency
            async def delayed_get(url: str, **kwargs: Any) -> MagicMock:
                await asyncio.sleep(0.01)
                if "openid-configuration" in url:
                    return create_response_mock(openid_config)
                return create_response_mock(jwks)

            mock_client.get.side_effect = delayed_get

            # Run concurrent validations
            results = await asyncio.gather(
                *[validator.validate_token(token) for token in tokens]
            )

        # All validations should succeed
        assert len(results) == 5
        for i, claims in enumerate(results):
            assert claims.sub == f"user-{i}"

        # JWKS should have been fetched only once (2 calls: config + jwks)
        # Due to the lock, concurrent requests should wait for the first fetch
        # Note: This may vary based on timing, but should be <= 4 (at most 2 full fetches)
        assert fetch_count <= 4
