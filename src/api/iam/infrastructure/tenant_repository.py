"""PostgreSQL implementation of ITenantRepository.

This repository manages tenant metadata storage in PostgreSQL.
Unlike GroupRepository, it doesn't need SpiceDB for membership hydration
since tenants have no complex relationships to reconstitute.

Write operations use the transactional outbox pattern - domain events are
collected from the aggregate and appended to the outbox table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import Tenant
from iam.domain.value_objects import TenantId
from iam.infrastructure.models import TenantModel
from iam.infrastructure.observability import (
    DefaultTenantRepositoryProbe,
    TenantRepositoryProbe,
)
from iam.infrastructure.outbox import IAMEventSerializer
from iam.ports.exceptions import DuplicateTenantNameError
from iam.ports.repositories import ITenantRepository

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class TenantRepository(ITenantRepository):
    """Repository managing PostgreSQL storage for Tenant aggregates.

    This implementation stores tenant metadata in PostgreSQL only.
    Tenants are simple aggregates with no complex relationships requiring
    SpiceDB hydration.

    Write operations use the transactional outbox pattern:
    - Domain events are collected from the aggregate
    - Events are appended to the outbox table (same transaction as PostgreSQL)
    - The outbox worker processes events if needed
    """

    def __init__(
        self,
        session: AsyncSession,
        outbox: "OutboxRepository",
        probe: TenantRepositoryProbe | None = None,
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
        self._probe = probe or DefaultTenantRepositoryProbe()
        self._serializer = serializer or IAMEventSerializer()

    async def save(self, tenant: Tenant) -> None:
        """Persist tenant metadata to PostgreSQL, events to outbox.

        Uses the transactional outbox pattern: domain events are appended
        to the outbox table within the same database transaction.

        Args:
            tenant: The Tenant aggregate to persist

        Raises:
            DuplicateTenantNameError: If tenant name already exists
        """
        # Check name uniqueness
        existing = await self.get_by_name(tenant.name)
        if existing and existing.id.value != tenant.id.value:
            self._probe.duplicate_tenant_name(tenant.name)
            raise DuplicateTenantNameError(f"Tenant '{tenant.name}' already exists")

        try:
            # Upsert tenant metadata in PostgreSQL
            stmt = select(TenantModel).where(TenantModel.id == tenant.id.value)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()

            if model:
                # Update existing
                model.name = tenant.name
            else:
                # Create new
                model = TenantModel(
                    id=tenant.id.value,
                    name=tenant.name,
                )
                self._session.add(model)

            # Flush to catch integrity errors before outbox writes
            await self._session.flush()

            # Collect, serialize, and append events from the aggregate to outbox
            events = tenant.collect_events()
            for event in events:
                payload = self._serializer.serialize(event)
                await self._outbox.append(
                    event_type=type(event).__name__,
                    payload=payload,
                    occurred_at=event.occurred_at,
                    aggregate_type="tenant",
                    aggregate_id=tenant.id.value,
                )

            self._probe.tenant_saved(tenant.id.value)

        except IntegrityError as e:
            # Handle unique constraint violation
            if "ix_tenants_name" in str(e):
                self._probe.duplicate_tenant_name(tenant.name)
                raise DuplicateTenantNameError(
                    f"Tenant '{tenant.name}' already exists"
                ) from e
            raise

    async def get_by_id(self, tenant_id: TenantId) -> Tenant | None:
        """Fetch tenant metadata from PostgreSQL.

        Args:
            tenant_id: The unique identifier of the tenant

        Returns:
            The Tenant aggregate, or None if not found
        """
        # Query PostgreSQL for tenant metadata
        stmt = select(TenantModel).where(TenantModel.id == tenant_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        # Reconstitute tenant aggregate
        # Tenants are simple - no SpiceDB hydration needed
        tenant = Tenant(
            id=TenantId(value=model.id),
            name=model.name,
        )

        self._probe.tenant_retrieved(tenant.id.value)
        return tenant

    async def get_by_name(self, name: str) -> Tenant | None:
        """Fetch tenant by name from PostgreSQL.

        Args:
            name: The tenant name

        Returns:
            The Tenant aggregate, or None if not found
        """
        stmt = select(TenantModel).where(TenantModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        # Reconstitute tenant aggregate
        tenant = Tenant(
            id=TenantId(value=model.id),
            name=model.name,
        )

        self._probe.tenant_retrieved(tenant.id.value)
        return tenant

    async def list_all(self) -> list[Tenant]:
        """Fetch all tenants from PostgreSQL.

        Returns:
            List of all Tenant aggregates
        """
        stmt = select(TenantModel)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        # Reconstitute tenant aggregates
        tenants = [
            Tenant(
                id=TenantId(value=model.id),
                name=model.name,
            )
            for model in models
        ]

        self._probe.tenants_listed(len(tenants))
        return tenants

    async def delete(self, tenant: Tenant) -> bool:
        """Delete tenant from PostgreSQL.

        The tenant should have mark_for_deletion() called before this method
        to record the TenantDeleted event.

        Args:
            tenant: The Tenant aggregate to delete (with deletion event recorded)

        Returns:
            True if deleted, False if not found
        """
        stmt = select(TenantModel).where(TenantModel.id == tenant.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        # Collect and append deletion event to outbox before deletion
        events = tenant.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="tenant",
                aggregate_id=tenant.id.value,
            )

        # Delete from PostgreSQL
        await self._session.delete(model)
        await self._session.flush()

        self._probe.tenant_deleted(tenant.id.value)
        return True
