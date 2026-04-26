"""Shared helper for parsing encryption key configuration.

The encryption_key setting may contain a comma-separated list of Fernet keys
(e.g. "key1,key2") to support key rotation. This module provides a single
canonical parser so every dependency that needs the key list behaves
identically — trimming whitespace and ignoring blank segments.
"""

from __future__ import annotations


def parse_encryption_keys(raw: str) -> list[str]:
    """Parse a comma-separated encryption-key string into a list of keys.

    Each segment is stripped of leading/trailing whitespace; empty segments
    (produced by trailing commas or double commas) are discarded.

    Args:
        raw: The raw secret string value from settings.encryption_key.

    Returns:
        A non-empty list of Fernet key strings.

    Example::

        parse_encryption_keys("key1, key2, ")
        # → ["key1", "key2"]
    """
    return [k.strip() for k in raw.split(",") if k.strip()]
