"""API Key application service for IAM bounded context.

Orchestrates API key lifecycle management including creation, validation,
and revocation with proper security handling.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.value_objects import CurrentUser
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_subject,
)
from shared_kernel.authorization.protocols import AuthorizationProvider
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
        authz: AuthorizationProvider,
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
        self._authz = authz

    async def create_api_key(
        self,
        created_by_user_id: UserId,
        name: str,
        expires_in_days: int,
        tenant_id: TenantId,
    ) -> tuple[APIKey, str]:
        """Create a new API key for a user.

        Generates a secure secret, hashes it, creates the aggregate,
        and persists it. Returns both the aggregate and the plaintext
        secret - the secret is only available at creation time.

        Args:
            created_by_user_id: The user who is creating this key (audit trail)
            name: A descriptive name for the key
            expires_in_days: Number of days until expiration
            tenant_id: The tenant in which the API key will be created
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

    async def list_api_keys(
        self,
        tenant_id: TenantId,
        current_user: CurrentUser,
        created_by_user_id: UserId | None = None,
    ) -> list[APIKey]:
        """List API keys with optional filters.

        Args:
            created_by_user_id: Optional filter for keys created by this user
            tenant_id: The tenant in which the list operation will be performed

        Returns:
            List of APIKey aggregates matching all provided filters
        """
        # Use SpiceDB to find all API keys the current user can view
        try:
            api_key_ids = await self._authz.lookup_resources(
                resource_type=ResourceType.API_KEY.value,
                permission=Permission.VIEW.value,
                subject=format_subject(ResourceType.USER, current_user.user_id.value),
            )

            keys = await self._api_key_repository.list(
                api_key_ids=[APIKeyId(value=key) for key in api_key_ids],
                tenant_id=tenant_id,
                created_by_user_id=created_by_user_id,
            )

            self._probe.api_key_list_retrieved(
                user_id=created_by_user_id.value if created_by_user_id else None,
                count=len(keys),
            )
            return keys
        except Exception as e:
            self._probe.api_key_list_retrieval_failed(
                user_id=created_by_user_id.value if created_by_user_id else None,
                reason=repr(e),
            )
            raise

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
            tenant_id: The tenant in which the revocation will occur
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

        Delegates prefix extraction and hash verification to the repository,
        then checks validity (not revoked, not expired) and updates last_used_at.

        Args:
            secret: The plaintext API key secret to validate

        Returns:
            The APIKey aggregate if valid, None otherwise
        """
        # Repository handles prefix-based lookup; we inject verification functions
        api_key = await self._api_key_repository.get_verified_key(
            secret=secret,
            extract_prefix_fn=extract_prefix,
            verify_hash_fn=verify_api_key_secret,
        )
        if api_key is None:
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
