"""OAuth2 authorization code flow routes with PKCE.

Implements OIDC SSO for Kartograph API. Uses PKCE (Proof Key for Code Exchange)
for enhanced security, which is required for public clients and recommended
for all OAuth2 implementations.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from auth.observability import AuthFlowProbe, DefaultAuthFlowProbe
from infrastructure.settings import OIDCSettings, get_oidc_settings

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory PKCE state storage (for walking skeleton - consider Redis for production)
_pkce_states: dict[str, dict[str, str]] = {}


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge.

    Uses S256 challenge method as recommended by RFC 7636.

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return code_verifier, code_challenge


def get_oidc_settings_dep() -> OIDCSettings:
    """Dependency for OIDC settings."""
    return get_oidc_settings()


def get_auth_probe_dep() -> AuthFlowProbe:
    """Dependency for auth flow probe."""
    return DefaultAuthFlowProbe()


def get_base_url_dep() -> str:
    """Dependency for base URL.

    In production, this should be configured via environment variable.
    For the walking skeleton, we use a sensible default.
    """
    # TODO: Make this configurable via settings
    return "http://localhost:8000"


@router.get("/login")
async def login(
    redirect_uri: str = Query(default="/docs"),
    settings: OIDCSettings = Depends(get_oidc_settings_dep),
    probe: AuthFlowProbe = Depends(get_auth_probe_dep),
    base_url: str = Depends(get_base_url_dep),
) -> RedirectResponse:
    """Initiate OIDC login flow.

    Generates PKCE challenge and redirects to IdP authorization endpoint.

    Args:
        redirect_uri: Where to redirect after successful auth (default: /docs)

    Returns:
        Redirect response to IdP authorization endpoint
    """
    probe.login_initiated(redirect_uri=redirect_uri)

    # Generate PKCE pair
    code_verifier, code_challenge = _generate_pkce_pair()

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store PKCE verifier and redirect_uri for callback
    _pkce_states[state] = {
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }

    # Get authorization endpoint from OIDC discovery
    try:
        async with httpx.AsyncClient() as client:
            discovery_url = f"{settings.issuer_url}/.well-known/openid-configuration"
            discovery_response = await client.get(discovery_url)
            discovery = discovery_response.json()
            auth_endpoint = discovery["authorization_endpoint"]
    except httpx.HTTPError as e:
        probe.discovery_failed(error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"OIDC discovery failed: {e}",
        ) from e
    except KeyError as e:
        probe.discovery_failed(error=f"Missing key in discovery: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"OIDC discovery failed: missing {e}",
        ) from e

    # Build authorization URL with query parameters
    callback_uri = f"{base_url}/auth/callback"
    params = {
        "client_id": settings.client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": callback_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{auth_endpoint}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    settings: OIDCSettings = Depends(get_oidc_settings_dep),
    probe: AuthFlowProbe = Depends(get_auth_probe_dep),
    base_url: str = Depends(get_base_url_dep),
) -> RedirectResponse:
    """Handle OIDC callback.

    Exchanges authorization code for tokens using PKCE verifier.
    Sets access token in httponly cookie.

    Args:
        code: Authorization code from IdP
        state: State parameter for CSRF validation

    Returns:
        Redirect response to original destination with token cookie
    """
    probe.callback_received(state=state)

    # Validate state
    if state not in _pkce_states:
        probe.invalid_state(state=state)
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    pkce_data = _pkce_states.pop(state)
    code_verifier = pkce_data["code_verifier"]
    redirect_uri = pkce_data["redirect_uri"]

    # Get token endpoint from discovery
    try:
        async with httpx.AsyncClient() as client:
            discovery_url = f"{settings.issuer_url}/.well-known/openid-configuration"
            discovery_response = await client.get(discovery_url)
            discovery = discovery_response.json()
            token_endpoint = discovery["token_endpoint"]

            # Exchange code for tokens
            callback_uri = f"{base_url}/auth/callback"
            token_response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.client_id,
                    "client_secret": settings.client_secret.get_secret_value(),
                    "code": code,
                    "redirect_uri": callback_uri,
                    "code_verifier": code_verifier,
                },
            )
    except httpx.HTTPError as e:
        probe.token_exchange_failed(error=str(e))
        raise HTTPException(
            status_code=401,
            detail=f"Token exchange failed: {e}",
        ) from e

    if token_response.status_code != 200:
        error_detail = token_response.json().get("error_description", "Unknown error")
        probe.token_exchange_failed(error=error_detail)
        raise HTTPException(
            status_code=401,
            detail=f"Token exchange failed: {error_detail}",
        )

    tokens = token_response.json()
    access_token = tokens["access_token"]

    # Log success (we don't decode the token here for simplicity)
    probe.token_exchange_success(user_id="<unknown>")

    # Redirect to original destination with token in cookie
    response = RedirectResponse(url=redirect_uri)
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=True,  # Set to False for local dev if needed
        samesite="lax",
    )
    return response
