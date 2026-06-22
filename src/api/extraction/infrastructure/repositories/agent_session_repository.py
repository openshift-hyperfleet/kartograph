"""PostgreSQL repository for extraction agent sessions."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode
from extraction.infrastructure.models.agent_session import ExtractionAgentSessionModel
from extraction.ports.repositories import IExtractionAgentSessionRepository
from sqlalchemy import column, table

_knowledge_graphs = table(
    "knowledge_graphs",
    column("id"),
    column("tenant_id"),
)


class ExtractionAgentSessionRepository(IExtractionAgentSessionRepository):
    """Persist and query extraction session records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, session: ExtractionAgentSession) -> None:
        stmt = select(ExtractionAgentSessionModel).where(
            ExtractionAgentSessionModel.id == session.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = ExtractionAgentSessionModel(
                id=session.id,
                user_id=session.user_id,
                knowledge_graph_id=session.knowledge_graph_id,
                mode=session.mode.value,
                graph_management_ui_mode=(
                    session.graph_management_ui_mode.value
                    if session.graph_management_ui_mode is not None
                    else None
                ),
                message_history=session.message_history,
                runtime_context=session.runtime_context,
                created_at=session.created_at,
                updated_at=session.updated_at,
                archived_at=session.archived_at,
            )
            self._session.add(model)
        else:
            model.message_history = session.message_history
            model.runtime_context = session.runtime_context
            model.graph_management_ui_mode = (
                session.graph_management_ui_mode.value
                if session.graph_management_ui_mode is not None
                else None
            )
            model.updated_at = session.updated_at
            model.archived_at = session.archived_at
        await self._session.flush()
        await self._session.commit()

    async def get_by_id(self, session_id: str) -> ExtractionAgentSession | None:
        stmt = select(ExtractionAgentSessionModel).where(
            ExtractionAgentSessionModel.id == session_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def get_active_by_id_for_scope(
        self,
        *,
        session_id: str,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> ExtractionAgentSession | None:
        stmt = (
            select(ExtractionAgentSessionModel)
            .join(
                _knowledge_graphs,
                _knowledge_graphs.c.id
                == ExtractionAgentSessionModel.knowledge_graph_id,
            )
            .where(
                ExtractionAgentSessionModel.id == session_id,
                ExtractionAgentSessionModel.knowledge_graph_id == knowledge_graph_id,
                _knowledge_graphs.c.tenant_id == tenant_id,
                ExtractionAgentSessionModel.archived_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_active_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession | None:
        stmt = (
            select(ExtractionAgentSessionModel)
            .where(
                ExtractionAgentSessionModel.user_id == user_id,
                ExtractionAgentSessionModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionAgentSessionModel.mode == mode.value,
                ExtractionAgentSessionModel.archived_at.is_(None),
            )
            .order_by(desc(ExtractionAgentSessionModel.updated_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_active_by_ui_mode(
        self,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession | None:
        stmt = (
            select(ExtractionAgentSessionModel)
            .where(
                ExtractionAgentSessionModel.user_id == user_id,
                ExtractionAgentSessionModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionAgentSessionModel.graph_management_ui_mode == ui_mode.value,
                ExtractionAgentSessionModel.archived_at.is_(None),
            )
            .order_by(desc(ExtractionAgentSessionModel.updated_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list_active_by_user_and_kg(
        self,
        user_id: str,
        knowledge_graph_id: str,
    ) -> list[ExtractionAgentSession]:
        stmt = (
            select(ExtractionAgentSessionModel)
            .where(
                ExtractionAgentSessionModel.user_id == user_id,
                ExtractionAgentSessionModel.knowledge_graph_id == knowledge_graph_id,
                ExtractionAgentSessionModel.archived_at.is_(None),
            )
            .order_by(desc(ExtractionAgentSessionModel.updated_at))
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def list_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode | None = None,
    ) -> list[ExtractionAgentSession]:
        stmt = select(ExtractionAgentSessionModel).where(
            ExtractionAgentSessionModel.user_id == user_id,
            ExtractionAgentSessionModel.knowledge_graph_id == knowledge_graph_id,
        )
        if mode is not None:
            stmt = stmt.where(ExtractionAgentSessionModel.mode == mode.value)
        stmt = stmt.order_by(desc(ExtractionAgentSessionModel.updated_at))
        result = await self._session.execute(stmt)
        return [self._to_domain(model) for model in result.scalars().all()]

    def _to_domain(self, model: ExtractionAgentSessionModel) -> ExtractionAgentSession:
        ui_mode = (
            GraphManagementUiMode(model.graph_management_ui_mode)
            if model.graph_management_ui_mode
            else None
        )
        return ExtractionAgentSession(
            id=model.id,
            user_id=model.user_id,
            knowledge_graph_id=model.knowledge_graph_id,
            mode=ExtractionSessionMode(model.mode),
            graph_management_ui_mode=ui_mode,
            message_history=list(model.message_history or []),
            runtime_context=dict(model.runtime_context or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            archived_at=model.archived_at,
        )
