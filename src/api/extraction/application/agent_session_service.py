"""Application service for extraction agent session lifecycle."""

from __future__ import annotations

from ulid import ULID

from extraction.application.skill_resolution_service import (
    ExtractionSkillResolutionService,
)
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import ExtractionSessionMode
from extraction.ports.repositories import IExtractionAgentSessionRepository


class ExtractionAgentSessionService:
    """Orchestrates session create/get/list/archive behaviors by scope."""

    def __init__(
        self,
        repository: IExtractionAgentSessionRepository,
        skill_resolution_service: ExtractionSkillResolutionService | None = None,
    ) -> None:
        self._repository = repository
        self._skill_resolution_service = skill_resolution_service

    async def get_or_create_active_session(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession:
        existing = await self._repository.find_active_by_scope(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )
        if existing is not None:
            return existing

        session = ExtractionAgentSession(
            id=str(ULID()),
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )
        if self._skill_resolution_service is not None:
            resolved = await self._skill_resolution_service.resolve_for_session(
                knowledge_graph_id=knowledge_graph_id,
                mode=mode,
            )
            session.runtime_context["agent_configuration"] = {
                "system_prompt": resolved.system_prompt,
                "prompt_hierarchy": list(resolved.prompt_hierarchy),
                "guardrails": list(resolved.guardrails),
                "skills": dict(resolved.skills),
            }
        await self._repository.save(session)
        return session

    async def clear_chat(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession:
        active = await self._repository.find_active_by_scope(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )
        if active is not None:
            active.archive()
            await self._repository.save(active)

        return await self.get_or_create_active_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )

    async def list_sessions(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode | None = None,
    ) -> list[ExtractionAgentSession]:
        return await self._repository.list_by_scope(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )

    async def archive_session(self, session_id: str) -> ExtractionAgentSession | None:
        session = await self._repository.get_by_id(session_id)
        if session is None:
            return None
        if session.is_active:
            session.archive()
            await self._repository.save(session)
        return session

