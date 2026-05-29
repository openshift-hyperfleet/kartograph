"""PostgreSQL repository for extraction agent sessions."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import ExtractionSessionMode
from extraction.infrastructure.models.agent_session import ExtractionAgentSessionModel
from extraction.ports.repositories import IExtractionAgentSessionRepository


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
        return ExtractionAgentSession(
            id=model.id,
            user_id=model.user_id,
            knowledge_graph_id=model.knowledge_graph_id,
            mode=ExtractionSessionMode(model.mode),
            message_history=list(model.message_history or []),
            runtime_context=dict(model.runtime_context or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            archived_at=model.archived_at,
        )

