"""JWT validation module for OIDC SSO.

Validates JWT tokens using OIDC provider's JWKS with caching.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

if TYPE_CHECKING:
    from shared_kernel.auth.observability import JWTValidatorProbe


@dataclass(frozen=True)
class TokenClaims:
    """Validated JWT claims."""

    sub: str
    preferred_username: str | None


class InvalidTokenError(Exception):
    """Raised when JWT validation fails."""

    pass


class JWTValidator:
    """Validates JWT tokens using OIDC provider's JWKS.

    Fetches JWKS from the OIDC provider and caches them for the configured TTL.
    Validates token signature, expiry, issuer, and audience.
    """

    def __init__(
        self,
        issuer_url: str,
        audience: str,
        probe: JWTValidatorProbe,
        user_id_claim: str = "sub",
        username_claim: str = "preferred_username",
        jwks_cache_ttl: timedelta = timedelta(hours=24),
    ):
        """Initialize the JWT validator.

        Args:
            issuer_url: The OIDC issuer URL (e.g., Keycloak realm URL).
            audience: Expected audience claim value.
            probe: Observability probe for logging events.
            user_id_claim: JWT claim to use for user ID (default: sub).
            username_claim: JWT claim to use for username (default: preferred_username).
            jwks_cache_ttl: How long to cache JWKS keys (default: 24 hours).
        """
        self._issuer_url = issuer_url.rstrip("/")
        self._audience = audience
        self._probe = probe
        self._user_id_claim = user_id_claim
        self._username_claim = username_claim
        self._jwks_cache_ttl = jwks_cache_ttl

        # JWKS cache
        self._jwks: dict[str, Any] | None = None
        self._jwks_fetched_at: datetime | None = None
        self._jwks_uri: str | None = None
        self._jwks_lock = asyncio.Lock()

    async def validate_token(self, token: str) -> TokenClaims:
        """Validate JWT and return claims.

        Args:
            token: The JWT token string.

        Returns:
            TokenClaims containing the validated claims.

        Raises:
            InvalidTokenError: If token is invalid, expired, or verification fails.
        """
        # First, do a quick check for malformed tokens
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as e:
            self._probe.token_validation_failed(reason=f"Malformed token: {e}")
            raise InvalidTokenError(f"Invalid token format: {e}") from e

        if not unverified_header:
            self._probe.token_validation_failed(reason="Missing token header")
            raise InvalidTokenError("Invalid token: missing header")

        # Get JWKS (from cache or fetch)
        jwks = await self._get_jwks()

        # Validate the token
        try:
            claims = jwt.decode(
                token=token,
                key=jwks,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer_url,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_iat": True,
                },
            )
        except ExpiredSignatureError as e:
            self._probe.token_validation_failed(reason="Token expired")
            raise InvalidTokenError("Token has expired") from e
        except JWTClaimsError as e:
            error_msg = str(e).lower()
            if "audience" in error_msg:
                self._probe.token_validation_failed(reason="Invalid audience")
                raise InvalidTokenError("Invalid audience claim") from e
            if "issuer" in error_msg:
                self._probe.token_validation_failed(reason="Invalid issuer")
                raise InvalidTokenError("Invalid issuer claim") from e
            self._probe.token_validation_failed(reason=f"Claims error: {e}")
            raise InvalidTokenError(f"Invalid token claims: {e}") from e
        except JWTError as e:
            error_msg = str(e).lower()
            if "signature" in error_msg:
                self._probe.token_validation_failed(reason="Invalid signature")
                raise InvalidTokenError("Invalid token signature") from e
            self._probe.token_validation_failed(reason=f"JWT error: {e}")
            raise InvalidTokenError(f"Invalid token: {e}") from e

        # Extract user ID claim
        user_id = claims.get(self._user_id_claim)
        if user_id is None:
            self._probe.token_validation_failed(
                reason=f"Missing {self._user_id_claim} claim"
            )
            raise InvalidTokenError(f"Missing required claim: {self._user_id_claim}")

        # Extract username claim
        username = claims.get(self._username_claim)

        self._probe.token_validated(user_id=str(user_id))

        return TokenClaims(
            sub=str(user_id),
            preferred_username=str(username) if username is not None else None,
        )

    async def _get_jwks(self) -> dict[str, Any]:
        """Get JWKS, fetching from issuer if cache expired.

        Returns:
            The JWKS dictionary with keys.

        Raises:
            InvalidTokenError: If JWKS cannot be fetched.
        """
        # Check if cache is still valid (without lock for quick check)
        if self._is_cache_valid():
            self._probe.jwks_cache_hit()
            return self._jwks  # type: ignore[return-value]

        # Acquire lock for fetching
        async with self._jwks_lock:
            # Double-check after acquiring lock
            if self._is_cache_valid():
                self._probe.jwks_cache_hit()
                return self._jwks  # type: ignore[return-value]

            # Fetch fresh JWKS
            return await self._fetch_jwks()

    def _is_cache_valid(self) -> bool:
        """Check if JWKS cache is still valid."""
        if self._jwks is None or self._jwks_fetched_at is None:
            return False

        now = datetime.now(tz=timezone.utc)
        return (now - self._jwks_fetched_at) < self._jwks_cache_ttl

    async def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch JWKS from the OIDC provider.

        First fetches the OpenID Connect discovery document, then fetches JWKS.

        Returns:
            The JWKS dictionary with keys.

        Raises:
            InvalidTokenError: If JWKS cannot be fetched.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Fetch OpenID configuration
                openid_config_url = (
                    f"{self._issuer_url}/.well-known/openid-configuration"
                )
                config_response = await client.get(openid_config_url)
                config_response.raise_for_status()
                openid_config = config_response.json()

                # Get JWKS URI from config
                jwks_uri = openid_config.get("jwks_uri")
                if not jwks_uri:
                    self._probe.jwks_fetch_failed(
                        error="Missing jwks_uri in OpenID configuration"
                    )
                    raise InvalidTokenError(
                        "OIDC provider missing jwks_uri in configuration"
                    )

                # Fetch JWKS
                jwks_response = await client.get(jwks_uri)
                jwks_response.raise_for_status()
                jwks = jwks_response.json()

                # Cache the JWKS
                self._jwks = jwks
                self._jwks_uri = jwks_uri
                self._jwks_fetched_at = datetime.now(tz=timezone.utc)

                key_count = len(jwks.get("keys", []))
                self._probe.jwks_fetched(key_count=key_count)

                return jwks

        except httpx.HTTPError as e:
            self._probe.jwks_fetch_failed(error=str(e))
            raise InvalidTokenError(
                f"Failed to fetch JWKS from OIDC provider: {e}"
            ) from e
        except Exception as e:
            if isinstance(e, InvalidTokenError):
                raise
            self._probe.jwks_fetch_failed(error=str(e))
            raise InvalidTokenError(f"Unexpected error fetching JWKS: {e}") from e
