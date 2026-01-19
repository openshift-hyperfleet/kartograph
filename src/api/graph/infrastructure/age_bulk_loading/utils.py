"""Utility functions for AGE bulk loading operations.

These are pure functions with no dependencies on other bulk loading components.
"""

from __future__ import annotations

import hashlib
import re

# Label name validation regex: only alphanumeric, underscore, must start with letter or underscore
# Max length 63 (PostgreSQL identifier limit)
_VALID_LABEL_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_MAX_LABEL_LENGTH = 63


def validate_label_name(label: str) -> None:
    """Validate that a label name is safe for use in SQL/Cypher queries.

    Args:
        label: The label name to validate

    Raises:
        ValueError: If the label is empty, too long, or contains invalid characters
    """
    if not label:
        raise ValueError("Invalid label name: label cannot be empty")

    if len(label) > _MAX_LABEL_LENGTH:
        raise ValueError(
            f"Invalid label name '{label}': exceeds maximum length of {_MAX_LABEL_LENGTH} characters"
        )

    if not _VALID_LABEL_PATTERN.match(label):
        raise ValueError(
            f"Invalid label name '{label}': must start with letter or underscore, "
            "and contain only alphanumeric characters and underscores"
        )


def compute_stable_hash(key: str) -> int:
    """Compute a stable hash for advisory lock keys.

    Uses SHA-256 to ensure consistent hashing across Python versions and processes.
    Returns a value that fits within PostgreSQL's signed 64-bit bigint range.

    Args:
        key: The string to hash (typically "graph_name:label")

    Returns:
        A stable integer hash suitable for pg_advisory_xact_lock
    """
    # SHA-256 produces 64 hex characters (256 bits)
    # Take first 16 hex characters (64 bits) and mask to signed 64-bit range
    hash_hex = hashlib.sha256(key.encode()).hexdigest()[:16]
    # Convert to int and mask to ensure it fits in signed 64-bit
    # 0x7FFFFFFFFFFFFFFF ensures non-negative value in signed 64-bit range
    return int(hash_hex, 16) & 0x7FFFFFFFFFFFFFFF


def escape_copy_value(value: str) -> str:
    """Escape special characters for PostgreSQL COPY format.

    COPY format uses tab as delimiter and newline as row separator.
    We need to escape these characters in data values.

    Escape sequences for COPY format:
    - Backslash -> \\\\
    - Tab -> \\t
    - Newline -> \\n
    - Carriage return -> \\r

    Args:
        value: The string value to escape

    Returns:
        The escaped string safe for COPY format
    """
    # Order matters: escape backslashes first
    result = value.replace("\\", "\\\\")
    result = result.replace("\t", "\\t")
    result = result.replace("\n", "\\n")
    result = result.replace("\r", "\\r")
    return result
