"""Session-bound auth tokens for sticky agent runtime HTTP endpoints."""

from __future__ import annotations

import secrets

RUNTIME_AUTH_HEADER = "X-Kartograph-Runtime-Auth"


def issue_runtime_auth_token() -> str:
    """Return a high-entropy token bound to one sticky runtime container."""
    return secrets.token_urlsafe(32)


def runtime_auth_matches(*, expected: str, provided: str) -> bool:
    """Constant-time comparison for runtime auth header values."""
    if not expected or not provided:
        return False
    return secrets.compare_digest(expected.strip(), provided.strip())
