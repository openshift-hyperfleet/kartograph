"""API key domain events for IAM context.

Domain events related to API key lifecycle management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class APIKeyCreated:
    """Event raised when a new API key is created.

    This event captures the creation of an API key for programmatic access.

    Attributes:
        api_key_id: The ULID of the created API key
        user_id: The ULID of the user who owns the key
        tenant_id: The ULID of the tenant the key belongs to
        name: The name/description of the key
        prefix: The key prefix for identification (e.g., karto_ab)
        occurred_at: When the event occurred (UTC)
    """

    api_key_id: str
    user_id: str
    tenant_id: str
    name: str
    prefix: str
    occurred_at: datetime


@dataclass(frozen=True)
class APIKeyRevoked:
    """Event raised when an API key is revoked.

    This event captures the revocation of an API key, making it unusable.
    SpiceDB relationships are preserved for audit trail.

    Attributes:
        api_key_id: The ULID of the revoked API key
        user_id: The ULID of the user who owned the key
        occurred_at: When the event occurred (UTC)
    """

    api_key_id: str
    user_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class APIKeyDeleted:
    """Event raised when an API key is permanently deleted.

    This event is used for cascade deletion (e.g., tenant deletion)
    and triggers cleanup of all SpiceDB relationships. Unlike revocation,
    this removes the key entirely from the system.

    Attributes:
        api_key_id: The ULID of the deleted API key
        user_id: The ULID of the user who owned the key
        tenant_id: The ULID of the tenant the key belonged to
        occurred_at: When the event occurred (UTC)
    """

    api_key_id: str
    user_id: str
    tenant_id: str
    occurred_at: datetime
