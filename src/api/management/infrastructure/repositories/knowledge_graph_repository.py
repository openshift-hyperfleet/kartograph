"""PostgreSQL implementation of IKnowledgeGraphRepository.

This repository manages KnowledgeGraph persistence in PostgreSQL and
uses the transactional outbox pattern for domain event publishing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.infrastructure.models import KnowledgeGraphModel
from management.infrastructure.observability import (
    DefaultKnowledgeGraphRepositoryProbe,
    KnowledgeGraphRepositoryProbe,
)
from management.infrastructure.outbox import ManagementEventSerializer
from management.ports.exceptions import DuplicateKnowledgeGraphNameError
from management.ports.repositories import IKnowledgeGraphRepository

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class KnowledgeGraphRepository(IKnowledgeGraphRepository):
    """Repository managing PostgreSQL storage for KnowledgeGraph aggregates.

    Write operations use the transactional outbox pattern:
    - Domain events are collected from the aggregate
    - Events are appended to the outbox table (same transaction as PostgreSQL)
    - The outbox worker processes events asynchronously
    """

    def __init__(
        self,
        session: AsyncSession,
        outbox: "OutboxRepository",
        probe: KnowledgeGraphRepositoryProbe | None = None,
        serializer: ManagementEventSerializer | None = None,
    ) -> None:
        self._session = session
        self._outbox = outbox
        self._probe = probe or DefaultKnowledgeGraphRepositoryProbe()
        self._serializer = serializer or ManagementEventSerializer()

    async def save(self, knowledge_graph: KnowledgeGraph) -> None:
        """Persist knowledge graph metadata to PostgreSQL, events to outbox.

        Raises:
            DuplicateKnowledgeGraphNameError: If name already exists in tenant
        """
        try:
            stmt = select(KnowledgeGraphModel).where(
                KnowledgeGraphModel.id == knowledge_graph.id.value
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()

            if model:
                model.name = knowledge_graph.name
                model.description = knowledge_graph.description
                model.updated_at = knowledge_graph.updated_at
            else:
                model = KnowledgeGraphModel(
                    id=knowledge_graph.id.value,
                    tenant_id=knowledge_graph.tenant_id,
                    workspace_id=knowledge_graph.workspace_id,
                    name=knowledge_graph.name,
                    description=knowledge_graph.description,
                    created_at=knowledge_graph.created_at,
                    updated_at=knowledge_graph.updated_at,
                )
                self._session.add(model)

            await self._session.flush()

            events = knowledge_graph.collect_events()
            for event in events:
                payload = self._serializer.serialize(event)
                await self._outbox.append(
                    event_type=type(event).__name__,
                    payload=payload,
                    occurred_at=event.occurred_at,
                    aggregate_type="knowledge_graph",
                    aggregate_id=knowledge_graph.id.value,
                )

            self._probe.knowledge_graph_saved(
                knowledge_graph.id.value, knowledge_graph.tenant_id
            )

        except IntegrityError as e:
            if "uq_knowledge_graphs_tenant_name" in str(e):
                self._probe.duplicate_knowledge_graph_name(
                    knowledge_graph.name, knowledge_graph.tenant_id
                )
                raise DuplicateKnowledgeGraphNameError(
                    f"Knowledge graph '{knowledge_graph.name}' already exists "
                    f"in tenant '{knowledge_graph.tenant_id}'"
                ) from e
            raise

    async def get_by_id(
        self, knowledge_graph_id: KnowledgeGraphId
    ) -> KnowledgeGraph | None:
        stmt = select(KnowledgeGraphModel).where(
            KnowledgeGraphModel.id == knowledge_graph_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.knowledge_graph_not_found(knowledge_graph_id.value)
            return None

        self._probe.knowledge_graph_retrieved(knowledge_graph_id.value)
        return self._to_domain(model)

    async def find_by_tenant(
        self, tenant_id: str, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[KnowledgeGraph], int]:
        # Count query
        count_stmt = (
            select(func.count())
            .select_from(KnowledgeGraphModel)
            .where(KnowledgeGraphModel.tenant_id == tenant_id)
        )
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        # Paginated query
        stmt = (
            select(KnowledgeGraphModel)
            .where(KnowledgeGraphModel.tenant_id == tenant_id)
            .offset(offset)
            .limit(limit)
            .order_by(KnowledgeGraphModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        kgs = [self._to_domain(model) for model in models]
        self._probe.knowledge_graphs_listed(tenant_id, len(kgs))
        return kgs, total

    async def delete(self, knowledge_graph: KnowledgeGraph) -> bool:
        stmt = select(KnowledgeGraphModel).where(
            KnowledgeGraphModel.id == knowledge_graph.id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        events = knowledge_graph.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="knowledge_graph",
                aggregate_id=knowledge_graph.id.value,
            )

        await self._session.delete(model)
        await self._session.flush()

        self._probe.knowledge_graph_deleted(knowledge_graph.id.value)
        return True

    def _to_domain(self, model: KnowledgeGraphModel) -> KnowledgeGraph:
        """Reconstitute aggregate from database state without generating events."""
        return KnowledgeGraph(
            id=KnowledgeGraphId(value=model.id),
            tenant_id=model.tenant_id,
            workspace_id=model.workspace_id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
