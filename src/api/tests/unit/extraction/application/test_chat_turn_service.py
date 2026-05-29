"""Unit tests for ExtractionChatTurnService."""

from __future__ import annotations

from dataclasses import replace

import pytest

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.application.chat_turn_service import ExtractionChatTurnService
from extraction.application.skill_resolution_service import ExtractionSkillResolutionService
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import (
    ExtractionSessionMode,
    GraphManagementUiMode,
    IngestionReadinessSnapshot,
)
from extraction.infrastructure.deterministic_chat_agent import DeterministicExtractionChatAgent
from extraction.infrastructure.workload_runtime import InMemoryStickySessionRuntimeManager


class _InMemoryAgentSessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, ExtractionAgentSession] = {}

    async def save(self, session: ExtractionAgentSession) -> None:
        self._sessions[session.id] = replace(session)

    async def get_by_id(self, session_id: str) -> ExtractionAgentSession | None:
        session = self._sessions.get(session_id)
        return replace(session) if session else None

    async def find_active_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession | None:
        for session in self._sessions.values():
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
        return []


class _StaticIngestionReadinessReader:
    def __init__(self, snapshot: IngestionReadinessSnapshot) -> None:
        self._snapshot = snapshot

    async def read_for_knowledge_graph(
        self, *, knowledge_graph_id: str
    ) -> IngestionReadinessSnapshot:
        return self._snapshot


class _StaticSkillResolutionService:
    async def resolve_for_graph_management_turn(self, **kwargs):
        return type(
            "_Resolved",
            (),
            {
                "system_prompt": "system",
                "prompt_hierarchy": ("platform",),
                "guardrails": ("scope",),
                "skills": {"ui_mode_framing": "test overlay"},
            },
        )()


@pytest.mark.asyncio
async def test_stream_chat_turn_persists_assistant_reply() -> None:
    repo = _InMemoryAgentSessionRepository()
    sticky = InMemoryStickySessionRuntimeManager()
    session_service = ExtractionAgentSessionService(repository=repo)
    service = ExtractionChatTurnService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(
            IngestionReadinessSnapshot(1, 1),
        ),
        sticky_runtime_manager=sticky,
        chat_agent=DeterministicExtractionChatAgent(),
    )

    events = [
        event
        async for event in service.stream_chat_turn(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            message="Help me design entity types",
        )
    ]

    assert events[-1]["type"] == "done"
    assert events[-1]["ok"] is True
    active = await repo.find_active_by_scope("user-1", "kg-1", ExtractionSessionMode.SCHEMA_BOOTSTRAP)
    assert active is not None
    assert active.message_history[-2]["role"] == "user"
    assert active.message_history[-1]["role"] == "assistant"
    assert active.runtime_context["sticky_runtime"]["container_id"]


@pytest.mark.asyncio
async def test_stream_chat_turn_wait_when_job_package_unprepared() -> None:
    repo = _InMemoryAgentSessionRepository()
    sticky = InMemoryStickySessionRuntimeManager()
    session_service = ExtractionAgentSessionService(repository=repo)
    service = ExtractionChatTurnService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(
            IngestionReadinessSnapshot(2, 0),
        ),
        sticky_runtime_manager=sticky,
        chat_agent=DeterministicExtractionChatAgent(),
    )

    events = [
        event
        async for event in service.stream_chat_turn(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
            message="Run extraction on repo files",
        )
    ]

    assert any(event.get("type") == "wait" for event in events)
    done = events[-1]
    assert done["ok"] is True
    assert done.get("wait") is True
    active = await repo.find_active_by_scope(
        "user-1", "kg-1", ExtractionSessionMode.EXTRACTION_OPERATIONS
    )
    assert active is not None
    assert active.runtime_context["job_package"]["phase"] == "awaiting_job_package"
