"""API Key application service for IAM bounded context.

Orchestrates API key lifecycle management including creation, validation,
and revocation with proper security handling.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability.api_key_service_probe import (
    APIKeyServiceProbe,
    DefaultAPIKeyServiceProbe,
)
from iam.application.security import (
    extract_prefix,
    generate_api_key_secret,
    hash_api_key_secret,
    verify_api_key_secret,
)
from iam.domain.aggregates import APIKey
from iam.domain.value_objects import APIKeyId, TenantId, UserId
from iam.ports.exceptions import APIKeyNotFoundError
from iam.ports.repositories import IAPIKeyRepository


class APIKeyService:
    """Application service for API key management.

    Orchestrates API key creation, validation, and revocation with
    proper security handling. Manages database transactions.
    """

    def __init__(
        self,
        session: AsyncSession,
        api_key_repository: IAPIKeyRepository,
        probe: APIKeyServiceProbe | None = None,
    ):
        """Initialize APIKeyService with dependencies.

        Args:
            session: Database session for transaction management
            api_key_repository: Repository for API key persistence
            probe: Optional domain probe for observability
        """
        self._session = session
        self._api_key_repository = api_key_repository
        self._probe = probe or DefaultAPIKeyServiceProbe()

    async def create_api_key(
        self,
        created_by_user_id: UserId,
        tenant_id: TenantId,
        name: str,
        expires_in_days: int | None = None,
    ) -> tuple[APIKey, str]:
        """Create a new API key for a user.

        Generates a secure secret, hashes it, creates the aggregate,
        and persists it. Returns both the aggregate and the plaintext
        secret - the secret is only available at creation time.

        Args:
            created_by_user_id: The user who is creating this key (audit trail)
            tenant_id: The tenant this key belongs to
            name: A descriptive name for the key
            expires_in_days: Optional number of days until expiration

        Returns:
            Tuple of (APIKey aggregate, plaintext_secret)

        Raises:
            DuplicateAPIKeyNameError: If key name already exists for user
        """
        try:
            # Generate secret and hash
            plaintext_secret = generate_api_key_secret()
            key_hash = hash_api_key_secret(plaintext_secret)
            prefix = extract_prefix(plaintext_secret)

            # Calculate expiration
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

            # Create aggregate
            api_key = APIKey.create(
                created_by_user_id=created_by_user_id,
                tenant_id=tenant_id,
                name=name,
                key_hash=key_hash,
                prefix=prefix,
                expires_at=expires_at,
            )

            # Persist
            async with self._session.begin():
                await self._api_key_repository.save(api_key)

            self._probe.api_key_created(
                api_key_id=api_key.id.value,
                user_id=created_by_user_id.value,
                name=name,
            )
            return api_key, plaintext_secret

        except Exception as e:
            self._probe.api_key_creation_failed(
                user_id=created_by_user_id.value,
                error=str(e),
            )
            raise

    async def list_viewable_api_keys(
        self,
        viewable_ids: list[str],
        tenant_id: TenantId,
        created_by_user_id: UserId | None = None,
    ) -> list[APIKey]:
        """List API keys filtered by SpiceDB viewable IDs.

        This method enforces SpiceDB authorization by only returning keys
        whose IDs are in the viewable_ids list (from SpiceDB lookup_resources).
        Optionally filters to a specific user's keys.

        Args:
            viewable_ids: List of API key IDs the caller can view (from SpiceDB)
            tenant_id: The tenant to scope the list to
            created_by_user_id: Optional filter for keys created by this user

        Returns:
            List of APIKey aggregates that are both viewable and match filters
        """
        keys = await self._api_key_repository.list_viewable(
            viewable_ids=viewable_ids,
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
        )

        self._probe.api_key_list_retrieved(
            user_id=created_by_user_id.value if created_by_user_id else "filtered",
            count=len(keys),
        )
        return keys

    async def revoke_api_key(
        self,
        api_key_id: APIKeyId,
        user_id: UserId,
        tenant_id: TenantId,
    ) -> None:
        """Revoke an API key.

        Marks the key as revoked so it can no longer be used for authentication.

        Args:
            api_key_id: The ID of the key to revoke
            user_id: The user who owns the key (for access control)
            tenant_id: The tenant the key belongs to (for access control)

        Raises:
            APIKeyNotFoundError: If the key doesn't exist
            APIKeyAlreadyRevokedError: If the key is already revoked
        """
        try:
            async with self._session.begin():
                api_key = await self._api_key_repository.get_by_id(
                    api_key_id, user_id, tenant_id
                )

                if api_key is None:
                    raise APIKeyNotFoundError(f"API key {api_key_id.value} not found")

                # This will raise APIKeyAlreadyRevokedError if already revoked
                api_key.revoke()
                await self._api_key_repository.save(api_key)

            self._probe.api_key_revoked(
                api_key_id=api_key_id.value,
                user_id=user_id.value,
            )

        except Exception as e:
            self._probe.api_key_revocation_failed(
                api_key_id=api_key_id.value,
                error=str(e),
            )
            raise

    async def validate_and_get_key(self, secret: str) -> APIKey | None:
        """Validate an API key secret and return the key if valid.

        Looks up the key by prefix, verifies the secret hash, checks
        validity (not revoked, not expired), and updates last_used_at.

        Args:
            secret: The plaintext API key secret to validate

        Returns:
            The APIKey aggregate if valid, None otherwise
        """
        # Extract prefix for quick lookup
        prefix = extract_prefix(secret)

        # Look up by prefix
        api_key = await self._api_key_repository.get_by_prefix(prefix)
        if api_key is None:
            return None

        # Verify the secret against the hash
        if not verify_api_key_secret(secret, api_key.key_hash):
            return None

        # Check if key is valid (not revoked, not expired)
        if not api_key.is_valid():
            return None

        # Update last_used_at
        # Note: We don't call begin() here because SQLAlchemy auto-begins
        # a transaction when we executed the query above. We just commit
        # the existing transaction after saving.
        api_key.record_usage()
        await self._api_key_repository.save(api_key)
        await self._session.commit()

        return api_key
