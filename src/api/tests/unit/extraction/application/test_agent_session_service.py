"""Unit tests for ExtractionAgentSessionService."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import ExtractionSessionMode


class _InMemoryAgentSessionRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, ExtractionAgentSession] = {}

    async def save(self, session: ExtractionAgentSession) -> None:
        self._by_id[session.id] = replace(session)

    async def get_by_id(self, session_id: str) -> ExtractionAgentSession | None:
        session = self._by_id.get(session_id)
        return replace(session) if session else None

    async def find_active_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession | None:
        for session in self._by_id.values():
            if (
                session.user_id == user_id
                and session.knowledge_graph_id == knowledge_graph_id
                and session.mode == mode
                and session.archived_at is None
            ):
                return replace(session)
        return None

    async def list_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode | None = None,
    ) -> list[ExtractionAgentSession]:
        sessions = [
            replace(session)
            for session in self._by_id.values()
            if session.user_id == user_id
            and session.knowledge_graph_id == knowledge_graph_id
            and (mode is None or session.mode == mode)
        ]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)


class _StaticSkillResolutionService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ExtractionSessionMode]] = []

    async def resolve_for_session(
        self,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ):
        self.calls.append((knowledge_graph_id, mode))
        if mode == ExtractionSessionMode.SCHEMA_BOOTSTRAP:
            return type(
                "_Resolved",
                (),
                {
                    "system_prompt": "Bootstrap system prompt",
                    "prompt_hierarchy": ("platform", "mode"),
                    "guardrails": ("never leak credentials",),
                    "skills": {"schema_modeling": "bootstrap schema guidance"},
                },
            )()
        return type(
            "_Resolved",
            (),
            {
                "system_prompt": "Operations system prompt",
                "prompt_hierarchy": ("platform", "operations"),
                "guardrails": ("mutation logs only",),
                "skills": {"job_setup": "operations setup guidance"},
            },
        )()


@pytest.mark.asyncio
class TestExtractionAgentSessionService:
    async def test_reuses_active_session_for_same_scope(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        first = await service.get_or_create_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )
        second = await service.get_or_create_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )

        assert first.id == second.id

    async def test_scope_isolated_by_user(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        first = await service.get_or_create_active_session(
            user_id="alice",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )
        second = await service.get_or_create_active_session(
            user_id="bob",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )

        assert first.id != second.id

    async def test_scope_isolated_by_mode(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        bootstrap = await service.get_or_create_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )
        operations = await service.get_or_create_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )

        assert bootstrap.id != operations.id

    async def test_clear_chat_archives_old_session_and_creates_new_one(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        old_session = await service.get_or_create_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )
        old_session.message_history = [{"role": "user", "content": "hello"}]
        old_session.runtime_context = {"draft": "x"}
        old_session.updated_at = datetime.now(UTC)
        await repo.save(old_session)

        new_session = await service.clear_chat(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )

        archived = await repo.get_by_id(old_session.id)
        assert archived is not None
        assert archived.archived_at is not None
        assert new_session.id != old_session.id
        assert new_session.message_history == []
        assert new_session.runtime_context == {}

    async def test_list_sessions_includes_archived_history(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        first = await service.get_or_create_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )
        await service.clear_chat(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )

        sessions = await service.list_sessions(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        )

        assert len(sessions) == 2
        assert any(session.id == first.id and session.archived_at is not None for session in sessions)

    async def test_new_session_initializes_runtime_context_from_skill_resolution(self):
        repo = _InMemoryAgentSessionRepository()
        skill_resolution = _StaticSkillResolutionService()
        service = ExtractionAgentSessionService(
            repository=repo,
            skill_resolution_service=skill_resolution,
        )

        session = await service.get_or_create_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )

        assert "agent_configuration" in session.runtime_context
        config = session.runtime_context["agent_configuration"]
        assert config["system_prompt"] == "Bootstrap system prompt"
        assert config["skills"]["schema_modeling"] == "bootstrap schema guidance"
        assert skill_resolution.calls == [("kg-1", ExtractionSessionMode.SCHEMA_BOOTSTRAP)]

