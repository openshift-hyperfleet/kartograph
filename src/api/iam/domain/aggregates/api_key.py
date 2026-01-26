"""APIKey aggregate for IAM context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from iam.domain.events import APIKeyCreated, APIKeyRevoked
from iam.domain.value_objects import APIKeyId, TenantId, UserId

if TYPE_CHECKING:
    from iam.domain.events import DomainEvent


@dataclass
class APIKey:
    """APIKey aggregate representing a programmatic access credential.

    API keys provide an alternative to OIDC JWT tokens for programmatic
    access (CI pipelines, scripts, service integrations).

    Business rules:
    - API keys are tied to a user and tenant
    - Keys can be revoked but not unrevoked
    - Expired keys are invalid
    - Usage is tracked via last_used_at

    Event collection:
    - All mutating operations record domain events
    - Events can be collected via collect_events() for the outbox pattern
    """

    id: APIKeyId
    created_by_user_id: UserId
    tenant_id: TenantId
    name: str
    key_hash: str
    prefix: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    is_revoked: bool = False
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        created_by_user_id: UserId,
        tenant_id: TenantId,
        name: str,
        key_hash: str,
        prefix: str,
        expires_at: datetime,
    ) -> "APIKey":
        """Factory method for creating a new API key.

        This is the proper DDD way to create aggregates. It generates the ID,
        initializes the aggregate, and records the APIKeyCreated event.

        Args:
            created_by_user_id: The user who created this key (for audit trail)
            tenant_id: The tenant this key belongs to
            name: A descriptive name for the key
            key_hash: The hashed secret (never store plaintext)
            prefix: The key prefix for identification (e.g., karto_ab)
            expires_at: Required expiration datetime

        Returns:
            A new APIKey aggregate with APIKeyCreated event recorded
        """
        api_key = cls(
            id=APIKeyId.generate(),
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        api_key._pending_events.append(
            APIKeyCreated(
                api_key_id=api_key.id.value,
                user_id=created_by_user_id.value,
                tenant_id=tenant_id.value,
                name=name,
                prefix=prefix,
                occurred_at=datetime.now(UTC),
            )
        )
        return api_key

    def revoke(self) -> None:
        """Revoke this API key, making it unusable.

        Raises:
            APIKeyAlreadyRevokedError: If the key is already revoked
        """
        from iam.ports.exceptions import APIKeyAlreadyRevokedError

        if self.is_revoked:
            raise APIKeyAlreadyRevokedError(
                f"API key {self.id.value} is already revoked"
            )

        self.is_revoked = True
        self._pending_events.append(
            APIKeyRevoked(
                api_key_id=self.id.value,
                user_id=self.created_by_user_id.value,
                occurred_at=datetime.now(UTC),
            )
        )

    def record_usage(self) -> None:
        """Record that this API key was used.

        Updates the last_used_at timestamp to track key usage.
        """
        self.last_used_at = datetime.now(UTC)

    def is_valid(self) -> bool:
        """Check if this API key is valid for authentication.

        A key is valid if:
        - It is not revoked
        - It is not expired

        Returns:
            True if the key is valid, False otherwise
        """
        if self.is_revoked:
            return False

        if datetime.now(UTC) >= self.expires_at:
            return False

        return True

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear pending domain events.

        This method returns all domain events that have been recorded since
        the last call to collect_events(). It clears the internal list, so
        subsequent calls will return an empty list until new events are recorded.

        Returns:
            List of pending domain events
        """
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events
