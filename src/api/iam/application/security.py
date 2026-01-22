"""Security utilities for API key management.

Provides secure secret generation, hashing, and verification for API keys.
Uses cryptographically secure random generation and bcrypt for hashing.
"""

import secrets

import bcrypt

API_KEY_PREFIX = "karto_"


def generate_api_key_secret() -> str:
    """Generate a URL-safe API key with karto_ prefix.

    Generates 32 bytes of cryptographically secure random data
    and encodes it as a URL-safe base64 string with the karto_ prefix.

    The karto_ prefix aids in:
    - Secret scanning (easily identifiable in logs/code)
    - Key rotation (clear identification of key source)
    - Debugging (immediately recognizable as an API key)

    Returns:
        A URL-safe API key string with karto_ prefix (e.g., karto_abc123...)
    """
    # replace - with _ for ease of copy/paste. (Most IDEs will separate word selection at a `-`)
    random_part = secrets.token_urlsafe(32).replace("-", "_")
    return f"{API_KEY_PREFIX}{random_part}"


def extract_prefix(secret: str) -> str:
    """Extract the first 12 characters as prefix for identification.

    The prefix is stored alongside the hash to enable quick lookup
    without needing to hash the full secret for every comparison.

    Args:
        secret: The full API key secret

    Returns:
        The first 12 characters of the secret
    """
    return secret[:12]


def hash_api_key_secret(secret: str) -> str:
    """Hash an API key secret using bcrypt.

    Uses bcrypt with automatic salt generation for secure password hashing.
    The work factor is automatically determined by bcrypt's gensalt().

    Args:
        secret: The plaintext API key secret to hash

    Returns:
        The bcrypt hash as a string
    """
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def verify_api_key_secret(secret: str, key_hash: str) -> bool:
    """Verify a secret against its hash using constant-time comparison.

    Uses bcrypt's checkpw which performs constant-time comparison
    to prevent timing attacks.

    Args:
        secret: The plaintext API key secret to verify
        key_hash: The bcrypt hash to verify against

    Returns:
        True if the secret matches the hash, False otherwise
    """
    try:
        return bcrypt.checkpw(secret.encode(), key_hash.encode())
    except Exception:
        # Return False for any error (invalid hash format, etc.)
        return False
