"""Fake OIDC provider for testing without Keycloak.

A lightweight, in-memory OIDC provider that issues real JWTs signed
with a known RSA key pair. Implements just enough of the OpenID Connect
protocol to satisfy the JWTValidator:

- /.well-known/openid-configuration (discovery)
- /certs (JWKS endpoint)
- /protocol/openid-connect/token (password grant)

Usage as a standalone server:
    uv run python -m tests.fakes.oidc_provider --port 8180

Usage in tests:
    provider = FakeOIDCProvider(issuer_url="http://localhost:8180/realms/kartograph")
    token = provider.issue_token(user_id="alice-id", username="alice")
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@dataclass(frozen=True)
class FakeUser:
    user_id: str
    username: str
    email: str
    password: str


_DEFAULT_USERS = [
    FakeUser(
        user_id="alice-test-id",
        username="alice",
        email="alice@example.com",
        password="password",
    ),
    FakeUser(
        user_id="bob-test-id",
        username="bob",
        email="bob@example.com",
        password="password",
    ),
]


class FakeOIDCProvider:
    """In-memory OIDC provider that issues real JWTs with a test RSA key.

    This is a fake (not a mock): it maintains state, issues real tokens
    that can be verified, and implements the OIDC protocol correctly.
    """

    def __init__(
        self,
        issuer_url: str = "http://localhost:8180/realms/kartograph",
        client_id: str = "kartograph-api",
        client_secret: str = "kartograph-api-secret",
        users: list[FakeUser] | None = None,
        token_lifetime_seconds: int = 3600,
    ):
        self._issuer_url = issuer_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._users = {u.username: u for u in (users or _DEFAULT_USERS)}
        self._token_lifetime = token_lifetime_seconds

        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self._public_key = self._private_key.public_key()
        self._kid = "fake-test-key-1"

    @property
    def issuer_url(self) -> str:
        return self._issuer_url

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def client_secret(self) -> str:
        return self._client_secret

    def issue_token(
        self,
        user_id: str | None = None,
        username: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Issue a signed JWT for a user.

        If username is provided, looks up the user. Otherwise uses
        user_id and username directly.
        """
        from jose import jwt as jose_jwt

        if username and username in self._users:
            user = self._users[username]
            user_id = user.user_id
            email = user.email
        else:
            user_id = user_id or "unknown-user-id"
            username = username or "unknown"
            email = f"{username}@example.com"

        now = int(time.time())
        claims = {
            "sub": user_id,
            "preferred_username": username,
            "email": email,
            "iss": self._issuer_url,
            "aud": self._client_id,
            "iat": now,
            "exp": now + self._token_lifetime,
            "typ": "Bearer",
        }
        if extra_claims:
            claims.update(extra_claims)

        private_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        return jose_jwt.encode(
            claims,
            private_pem,
            algorithm="RS256",
            headers={"kid": self._kid},
        )

    def authenticate(self, username: str, password: str) -> str | None:
        """Authenticate a user and return a token, or None if invalid."""
        user = self._users.get(username)
        if user and user.password == password:
            return self.issue_token(username=username)
        return None

    def openid_configuration(self) -> dict[str, Any]:
        """Return the OpenID Connect discovery document."""
        return {
            "issuer": self._issuer_url,
            "authorization_endpoint": f"{self._issuer_url}/protocol/openid-connect/auth",
            "token_endpoint": f"{self._issuer_url}/protocol/openid-connect/token",
            "jwks_uri": f"{self._issuer_url}/protocol/openid-connect/certs",
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "password"],
        }

    def jwks(self) -> dict[str, Any]:
        """Return the JWKS (JSON Web Key Set) with the public key."""
        public_numbers = self._public_key.public_numbers()

        def _b64url(n: int, length: int) -> str:
            return (
                base64.urlsafe_b64encode(n.to_bytes(length, byteorder="big"))
                .rstrip(b"=")
                .decode("ascii")
            )

        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "kid": self._kid,
                    "alg": "RS256",
                    "n": _b64url(public_numbers.n, 256),
                    "e": _b64url(public_numbers.e, 3),
                }
            ]
        }


def create_oidc_app(provider: FakeOIDCProvider | None = None):
    """Create a FastAPI app that serves as a fake OIDC provider."""
    from fastapi import FastAPI, Form, HTTPException
    from fastapi.responses import JSONResponse

    if provider is None:
        provider = FakeOIDCProvider()

    app = FastAPI(title="Fake OIDC Provider")
    realm_prefix = "/realms/kartograph"

    @app.get(f"{realm_prefix}/.well-known/openid-configuration")
    def discovery():
        return JSONResponse(provider.openid_configuration())

    @app.get(f"{realm_prefix}/protocol/openid-connect/certs")
    def certs():
        return JSONResponse(provider.jwks())

    @app.post(f"{realm_prefix}/protocol/openid-connect/token")
    def token(
        grant_type: str = Form(...),
        username: str = Form(None),
        password: str = Form(None),
        client_id: str = Form(None),
        client_secret: str = Form(None),
        **kwargs,
    ):
        if grant_type != "password":
            raise HTTPException(400, "Only password grant supported in fake provider")

        access_token = provider.authenticate(username or "", password or "")
        if not access_token:
            raise HTTPException(401, "Invalid credentials")

        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        )

    return app


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Fake OIDC Provider")
    parser.add_argument("--port", type=int, default=8180)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    app = create_oidc_app()
    uvicorn.run(app, host=args.host, port=args.port)
