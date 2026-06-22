"""PostgreSQL implementation of IKnowledgeGraphRepository.

This repository manages KnowledgeGraph persistence in PostgreSQL and
uses the transactional outbox pattern for domain event publishing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from management.domain.aggregates import KnowledgeGraph
from management.domain.extraction_job_config import ExtractionJobConfigDocument
from management.domain.value_objects import (
    KnowledgeGraphMaintenanceRunRecord,
    KnowledgeGraphMaintenanceSchedule,
    KnowledgeGraphId,
    OntologyConfig,
    WorkspaceMode,
)
from management.infrastructure.models import KnowledgeGraphModel
from management.infrastructure.observability import (
    DefaultKnowledgeGraphRepositoryProbe,
    KnowledgeGraphRepositoryProbe,
)
from management.infrastructure.outbox import ManagementEventSerializer
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    KnowledgeGraphNotFoundError,
)
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
                model.workspace_mode = knowledge_graph.workspace_mode.value
                model.active_schema_bootstrap_session_id = (
                    knowledge_graph.active_schema_bootstrap_session_id
                )
                model.active_extraction_operations_session_id = (
                    knowledge_graph.active_extraction_operations_session_id
                )
                model.most_recent_completed_session_id = (
                    knowledge_graph.most_recent_completed_session_id
                )
                model.updated_at = knowledge_graph.updated_at
                model.maintenance_schedule = (
                    knowledge_graph.maintenance_schedule.to_dict()
                    if knowledge_graph.maintenance_schedule is not None
                    else None
                )
                model.maintenance_run_history = [
                    run.to_dict() for run in knowledge_graph.maintenance_run_history
                ]
            else:
                model = KnowledgeGraphModel(
                    id=knowledge_graph.id.value,
                    tenant_id=knowledge_graph.tenant_id,
                    workspace_id=knowledge_graph.workspace_id,
                    name=knowledge_graph.name,
                    description=knowledge_graph.description,
                    workspace_mode=knowledge_graph.workspace_mode.value,
                    active_schema_bootstrap_session_id=(
                        knowledge_graph.active_schema_bootstrap_session_id
                    ),
                    active_extraction_operations_session_id=(
                        knowledge_graph.active_extraction_operations_session_id
                    ),
                    most_recent_completed_session_id=(
                        knowledge_graph.most_recent_completed_session_id
                    ),
                    created_at=knowledge_graph.created_at,
                    updated_at=knowledge_graph.updated_at,
                    maintenance_schedule=(
                        knowledge_graph.maintenance_schedule.to_dict()
                        if knowledge_graph.maintenance_schedule is not None
                        else None
                    ),
                    maintenance_run_history=[
                        run.to_dict() for run in knowledge_graph.maintenance_run_history
                    ],
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

    async def find_by_tenant(self, tenant_id: str) -> list[KnowledgeGraph]:
        stmt = select(KnowledgeGraphModel).where(
            KnowledgeGraphModel.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        kgs = [self._to_domain(model) for model in models]
        self._probe.knowledge_graphs_listed(tenant_id, len(kgs))
        return kgs

    async def find_all(self) -> list[KnowledgeGraph]:
        stmt = select(KnowledgeGraphModel)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

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

    async def save_ontology(self, kg_id: str, config: OntologyConfig) -> None:
        """Update only the ontology JSONB column for the given KG.

        Performs a targeted UPDATE of the ``ontology`` column without
        touching outbox events or other aggregate fields.

        Args:
            kg_id: ULID string of the target KnowledgeGraph
            config: The OntologyConfig to persist
        """
        from sqlalchemy import update

        stmt = (
            update(KnowledgeGraphModel)
            .where(KnowledgeGraphModel.id == kg_id)
            .values(ontology=config.to_dict())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        # CursorResult.rowcount is always available for DML statements;
        # mypy's AsyncSession stub returns the broader Result[Any] type.
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise KnowledgeGraphNotFoundError(f"Knowledge graph '{kg_id}' not found")

    async def get_ontology(self, kg_id: str) -> OntologyConfig | None:
        """Read the ontology JSONB column for the given KG.

        Args:
            kg_id: ULID string of the target KnowledgeGraph

        Returns:
            Deserialized OntologyConfig, or None if column is NULL or KG not found
        """
        stmt = select(KnowledgeGraphModel).where(KnowledgeGraphModel.id == kg_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None or model.ontology is None:
            return None

        return OntologyConfig.from_dict(model.ontology)

    async def save_extraction_job_config(
        self,
        kg_id: str,
        config: ExtractionJobConfigDocument,
    ) -> None:
        from sqlalchemy import update

        stmt = (
            update(KnowledgeGraphModel)
            .where(KnowledgeGraphModel.id == kg_id)
            .values(extraction_job_config=config.to_dict())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise KnowledgeGraphNotFoundError(f"Knowledge graph '{kg_id}' not found")

    async def get_extraction_job_config(
        self, kg_id: str
    ) -> ExtractionJobConfigDocument | None:
        stmt = select(KnowledgeGraphModel).where(KnowledgeGraphModel.id == kg_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return ExtractionJobConfigDocument.from_dict(model.extraction_job_config)

    def _to_domain(self, model: KnowledgeGraphModel) -> KnowledgeGraph:
        """Reconstitute aggregate from database state without generating events."""
        ontology: OntologyConfig | None = None
        if model.ontology is not None:
            ontology = OntologyConfig.from_dict(model.ontology)
        maintenance_schedule: KnowledgeGraphMaintenanceSchedule | None = None
        if model.maintenance_schedule is not None:
            maintenance_schedule = KnowledgeGraphMaintenanceSchedule.from_dict(
                model.maintenance_schedule
            )
        maintenance_run_history = tuple(
            KnowledgeGraphMaintenanceRunRecord.from_dict(raw_run)
            for raw_run in (model.maintenance_run_history or [])
        )

        return KnowledgeGraph(
            id=KnowledgeGraphId(value=model.id),
            tenant_id=model.tenant_id,
            workspace_id=model.workspace_id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
            ontology=ontology,
            maintenance_schedule=maintenance_schedule,
            maintenance_run_history=maintenance_run_history,
            workspace_mode=WorkspaceMode(model.workspace_mode),
            active_schema_bootstrap_session_id=model.active_schema_bootstrap_session_id,
            active_extraction_operations_session_id=(
                model.active_extraction_operations_session_id
            ),
            most_recent_completed_session_id=model.most_recent_completed_session_id,
        )
