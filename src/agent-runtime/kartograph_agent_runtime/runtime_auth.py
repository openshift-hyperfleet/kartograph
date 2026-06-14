"""Runtime HTTP auth helpers for sticky session agent containers."""

from __future__ import annotations

import secrets

RUNTIME_AUTH_HEADER = "X-Kartograph-Runtime-Auth"


def runtime_auth_matches(*, expected: str, provided: str) -> bool:
    """Constant-time comparison for runtime auth header values."""
    if not expected or not provided:
        return False
    return secrets.compare_digest(expected.strip(), provided.strip())
