"""PostgreSQL implementation of IAPIKeyRepository.

This repository handles persistence of API keys to PostgreSQL.
The created_by_user_id field stores who created the key (audit trail),
while authorization (owner relationship) is managed by SpiceDB.

Write operations use the transactional outbox pattern - domain events are
collected from the aggregate and appended to the outbox table, rather than
writing directly to external services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import APIKey
from iam.domain.value_objects import APIKeyId, TenantId, UserId
from iam.infrastructure.models import APIKeyModel
from iam.infrastructure.observability import (
    APIKeyRepositoryProbe,
    DefaultAPIKeyRepositoryProbe,
)
from iam.infrastructure.outbox import IAMEventSerializer
from iam.ports.exceptions import DuplicateAPIKeyNameError
from iam.ports.repositories import IAPIKeyRepository

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class APIKeyRepository(IAPIKeyRepository):
    """Repository for APIKey aggregate persistence to PostgreSQL.

    This implementation stores API key metadata in PostgreSQL.
    The key_hash is stored for authentication lookup, but the plaintext
    secret is never persisted.

    Write operations use the transactional outbox pattern:
    - Domain events are collected from the aggregate
    - Events are appended to the outbox table (same transaction as PostgreSQL)
    - The outbox worker processes events asynchronously
    """

    def __init__(
        self,
        session: AsyncSession,
        outbox: "OutboxRepository",
        probe: APIKeyRepositoryProbe | None = None,
        serializer: IAMEventSerializer | None = None,
    ) -> None:
        """Initialize repository with database session and outbox.

        Args:
            session: AsyncSession from FastAPI dependency injection
            outbox: Outbox repository for the transactional outbox pattern
            probe: Optional domain probe for observability
            serializer: Optional event serializer for testability
        """
        self._session = session
        self._outbox = outbox
        self._probe = probe or DefaultAPIKeyRepositoryProbe()
        self._serializer = serializer or IAMEventSerializer()

    async def save(self, api_key: APIKey) -> None:
        """Persist API key metadata to PostgreSQL, events to outbox.

        Uses the transactional outbox pattern: domain events are appended
        to the outbox table within the same database transaction.

        Args:
            api_key: The APIKey aggregate to persist

        Raises:
            DuplicateAPIKeyNameError: If key name already exists for user in tenant
        """
        # Check for duplicate name (different ID, same user/tenant/name)
        existing = await self._get_by_name(
            api_key.name, api_key.created_by_user_id, api_key.tenant_id
        )
        if existing and existing.id != api_key.id.value:
            self._probe.duplicate_api_key_name(
                api_key.name,
                api_key.created_by_user_id.value,
                api_key.tenant_id.value,
            )
            raise DuplicateAPIKeyNameError(
                f"API key '{api_key.name}' already exists for user "
                f"{api_key.created_by_user_id.value} in tenant {api_key.tenant_id.value}"
            )

        # Check if API key already exists (upsert pattern)
        stmt = select(APIKeyModel).where(APIKeyModel.id == api_key.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            # Update existing
            model.name = api_key.name
            model.expires_at = api_key.expires_at
            model.last_used_at = api_key.last_used_at
            model.is_revoked = api_key.is_revoked
        else:
            # Create new
            model = APIKeyModel(
                id=api_key.id.value,
                created_by_user_id=api_key.created_by_user_id.value,
                tenant_id=api_key.tenant_id.value,
                name=api_key.name,
                key_hash=api_key.key_hash,
                prefix=api_key.prefix,
                expires_at=api_key.expires_at,
                last_used_at=api_key.last_used_at,
                is_revoked=api_key.is_revoked,
            )
            self._session.add(model)

        # Flush to catch integrity errors before outbox writes
        await self._session.flush()

        # Collect, serialize, and append events to outbox
        events = api_key.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="api_key",
                aggregate_id=api_key.id.value,
            )

        self._probe.api_key_saved(api_key.id.value, api_key.created_by_user_id.value)

    async def get_by_id(
        self, api_key_id: APIKeyId, user_id: UserId, tenant_id: TenantId
    ) -> APIKey | None:
        """Retrieve an API key by ID with user/tenant scoping.

        Args:
            api_key_id: The unique identifier of the API key
            user_id: The user who created the key (for access control)
            tenant_id: The tenant the key belongs to (for access control)

        Returns:
            The APIKey aggregate, or None if not found or access denied
        """
        stmt = select(APIKeyModel).where(
            and_(
                APIKeyModel.id == api_key_id.value,
                APIKeyModel.created_by_user_id == user_id.value,
                APIKeyModel.tenant_id == tenant_id.value,
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.api_key_not_found(api_key_id.value)
            return None

        self._probe.api_key_retrieved(api_key_id.value)
        return self._to_aggregate(model)

    async def get_by_key_hash(self, key_hash: str) -> APIKey | None:
        """Retrieve an API key by its hash for authentication.

        Args:
            key_hash: The hash of the API key secret

        Returns:
            The APIKey aggregate, or None if not found
        """
        stmt = select(APIKeyModel).where(APIKeyModel.key_hash == key_hash)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.api_key_not_found_by_hash()
            return None

        self._probe.api_key_retrieved(model.id)
        return self._to_aggregate(model)

    async def get_by_prefix(self, prefix: str) -> APIKey | None:
        """Retrieve an API key by its prefix for authentication.

        The prefix is the first 12 characters of the API key secret.
        This allows quick lookup before performing the more expensive
        hash verification.

        Args:
            prefix: The first 12 characters of the API key secret

        Returns:
            The APIKey aggregate, or None if not found
        """
        stmt = select(APIKeyModel).where(APIKeyModel.prefix == prefix)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.api_key_not_found_by_hash()
            return None

        self._probe.api_key_retrieved(model.id)
        return self._to_aggregate(model)

    async def list(
        self,
        api_key_ids: list[str] | None = None,
        tenant_id: TenantId | None = None,
        created_by_user_id: UserId | None = None,
    ) -> list[APIKey]:
        """List API keys with optional filters.

        This is a general-purpose list method. Filters are combined with AND logic.
        The repository doesn't know or care about authorization - it just filters
        by the provided criteria.

        Args:
            api_key_ids: Optional list of specific API key IDs to include
            tenant_id: Optional tenant to scope the list to
            created_by_user_id: Optional filter for keys created by this user

        Returns:
            List of APIKey aggregates matching all provided filters
        """
        conditions = []

        if api_key_ids is not None:
            if not api_key_ids:
                # Empty list means no results
                return []
            conditions.append(APIKeyModel.id.in_(api_key_ids))

        if tenant_id is not None:
            conditions.append(APIKeyModel.tenant_id == tenant_id.value)

        if created_by_user_id is not None:
            conditions.append(
                APIKeyModel.created_by_user_id == created_by_user_id.value
            )

        if conditions:
            stmt = select(APIKeyModel).where(and_(*conditions))
        else:
            stmt = select(APIKeyModel)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        api_keys = [self._to_aggregate(model) for model in models]
        self._probe.api_key_list_retrieved(
            created_by_user_id.value if created_by_user_id else "all", len(api_keys)
        )
        return api_keys

    async def delete(self, api_key: APIKey) -> bool:
        """Delete an API key from PostgreSQL.

        Args:
            api_key: The APIKey aggregate to delete

        Returns:
            True if deleted, False if not found
        """
        stmt = select(APIKeyModel).where(APIKeyModel.id == api_key.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.api_key_not_found(api_key.id.value)
            return False

        await self._session.delete(model)

        # Collect and append any pending events (e.g., APIKeyRevoked)
        events = api_key.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="api_key",
                aggregate_id=api_key.id.value,
            )

        self._probe.api_key_deleted(api_key.id.value)
        return True

    async def _get_by_name(
        self, name: str, created_by_user_id: UserId, tenant_id: TenantId
    ) -> APIKeyModel | None:
        """Internal helper to check for duplicate names.

        Args:
            name: The API key name
            created_by_user_id: The user who created the key
            tenant_id: The tenant the key belongs to

        Returns:
            The APIKeyModel if found, None otherwise
        """
        stmt = select(APIKeyModel).where(
            and_(
                APIKeyModel.name == name,
                APIKeyModel.created_by_user_id == created_by_user_id.value,
                APIKeyModel.tenant_id == tenant_id.value,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    def _to_aggregate(self, model: APIKeyModel) -> APIKey:
        """Convert SQLAlchemy model to domain aggregate.

        Args:
            model: The APIKeyModel to convert

        Returns:
            The APIKey domain aggregate
        """
        return APIKey(
            id=APIKeyId(value=model.id),
            created_by_user_id=UserId(value=model.created_by_user_id),
            tenant_id=TenantId(value=model.tenant_id),
            name=model.name,
            key_hash=model.key_hash,
            prefix=model.prefix,
            created_at=model.created_at,
            expires_at=model.expires_at,
            last_used_at=model.last_used_at,
            is_revoked=model.is_revoked,
        )
