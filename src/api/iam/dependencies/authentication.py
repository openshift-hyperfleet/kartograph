from functools import lru_cache

from fastapi.security import OAuth2AuthorizationCodeBearer

from iam.application.observability import (
    AuthenticationProbe,
    DefaultAuthenticationProbe,
)
from infrastructure.settings import get_oidc_settings
from shared_kernel.auth import JWTValidator
from shared_kernel.auth.observability import DefaultJWTValidatorProbe


def _create_oauth2_scheme() -> OAuth2AuthorizationCodeBearer:
    """Create OAuth2 security scheme for Swagger UI integration.

    Uses the OIDC issuer URL to configure authorization code flow endpoints.
    This enables Swagger UI's Authorize button to work with Keycloak.
    """
    issuer = get_oidc_settings().issuer_url

    return OAuth2AuthorizationCodeBearer(
        authorizationUrl=f"{issuer}/protocol/openid-connect/auth",
        tokenUrl=f"{issuer}/protocol/openid-connect/token",
        refreshUrl=f"{issuer}/protocol/openid-connect/token",
        scopes={
            "openid": "OpenID Connect",
            "profile": "User profile",
            "email": "User email",
        },
        auto_error=False,
    )


# Create OAuth2 security scheme for Swagger UI integration
oauth2_scheme = _create_oauth2_scheme()


@lru_cache
def get_jwt_validator() -> JWTValidator:
    """Get cached JWT validator.

    Uses lru_cache to ensure a single JWTValidator instance is reused across
    requests, enabling reuse of the instance-level JWKS cache.

    Returns:
        JWTValidator instance configured from OIDC settings.
    """
    settings = get_oidc_settings()
    probe = DefaultJWTValidatorProbe()
    return JWTValidator(
        issuer_url=settings.issuer_url,
        audience=settings.effective_audience,
        probe=probe,
        user_id_claim=settings.user_id_claim,
        username_claim=settings.username_claim,
    )


def get_authentication_probe() -> AuthenticationProbe:
    """Get AuthenticationProbe instance.

    Returns:
        DefaultAuthenticationProbe instance for observability
    """
    return DefaultAuthenticationProbe()
