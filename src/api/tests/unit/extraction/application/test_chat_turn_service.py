"""Unit tests for ExtractionChatTurnService."""

from __future__ import annotations

from dataclasses import replace

import pytest

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.application.chat_turn_service import ExtractionChatTurnService
from extraction.application.sticky_session_runtime_service import StickySessionRuntimeService
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import (
    ExtractionSessionMode,
    GraphManagementUiMode,
    IngestionReadinessSnapshot,
)
from extraction.infrastructure.deterministic_chat_agent import DeterministicExtractionChatAgent
from extraction.infrastructure.workload_credential_issuer import ScopedWorkloadCredentialIssuer
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


class _StaticBootstrapBuilder:
    async def build(self, **kwargs):
        return None


class _InstantHealthChecker:
    async def wait_until_healthy(self, **kwargs):
        yield "Assistant container is healthy"
        return

    async def is_healthy(self, **kwargs) -> bool:
        return True


def _build_chat_turn_service(
    *,
    readiness: IngestionReadinessSnapshot,
) -> tuple[ExtractionChatTurnService, _InMemoryAgentSessionRepository]:
    repo = _InMemoryAgentSessionRepository()
    sticky = InMemoryStickySessionRuntimeManager()
    session_service = ExtractionAgentSessionService(repository=repo)
    runtime_service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(readiness),
        sticky_runtime_manager=sticky,
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_InstantHealthChecker(),
        runtime_backend="memory",
        sticky_health_timeout_seconds=5.0,
    )
    service = ExtractionChatTurnService(
        session_service=session_service,
        runtime_service=runtime_service,
        chat_agent=DeterministicExtractionChatAgent(),
    )
    return service, repo


class _UsageEmittingChatAgent:
    async def stream_turn(self, **kwargs):
        yield {
            "type": "done",
            "ok": True,
            "reply": "Designed schema.",
            "usage": {
                "input_tokens": 800,
                "output_tokens": 200,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "cost_usd": 0.25,
            },
        }


@pytest.mark.asyncio
async def test_stream_chat_turn_accumulates_token_usage_in_session_journal() -> None:
    repo = _InMemoryAgentSessionRepository()
    sticky = InMemoryStickySessionRuntimeManager()
    session_service = ExtractionAgentSessionService(repository=repo)
    runtime_service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(IngestionReadinessSnapshot(1, 1)),
        sticky_runtime_manager=sticky,
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_InstantHealthChecker(),
        runtime_backend="memory",
        sticky_health_timeout_seconds=5.0,
    )
    service = ExtractionChatTurnService(
        session_service=session_service,
        runtime_service=runtime_service,
        chat_agent=_UsageEmittingChatAgent(),
    )

    events = [
        event
        async for event in service.stream_chat_turn(
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            message="Design entity types",
        )
    ]

    assert events[-1]["ok"] is True
    active = await repo.find_active_by_scope("user-1", "kg-1", ExtractionSessionMode.SCHEMA_BOOTSTRAP)
    assert active is not None
    journal = active.runtime_context["mutation_journal"]
    assert journal["input_tokens"] == 800
    assert journal["output_tokens"] == 200
    assert journal["cost_usd"] == 0.25


@pytest.mark.asyncio
async def test_stream_chat_turn_persists_assistant_reply() -> None:
    service, repo = _build_chat_turn_service(readiness=IngestionReadinessSnapshot(1, 1))

    events = [
        event
        async for event in service.stream_chat_turn(
            tenant_id="tenant-1",
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


class _TokenCapturingChatAgent(DeterministicExtractionChatAgent):
    def __init__(self) -> None:
        self.last_workload_token: str | None = None

    async def stream_turn(self, **kwargs):
        self.last_workload_token = kwargs.get("workload_token")
        async for event in super().stream_turn(**kwargs):
            yield event


@pytest.mark.asyncio
async def test_stream_chat_turn_passes_fresh_workload_token_to_agent() -> None:
    repo = _InMemoryAgentSessionRepository()
    sticky = InMemoryStickySessionRuntimeManager()
    session_service = ExtractionAgentSessionService(repository=repo)
    runtime_service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(IngestionReadinessSnapshot(1, 1)),
        sticky_runtime_manager=sticky,
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_InstantHealthChecker(),
        runtime_backend="memory",
        sticky_health_timeout_seconds=5.0,
    )
    chat_agent = _TokenCapturingChatAgent()
    service = ExtractionChatTurnService(
        session_service=session_service,
        runtime_service=runtime_service,
        chat_agent=chat_agent,
        credential_issuer=ScopedWorkloadCredentialIssuer(default_ttl=__import__("datetime").timedelta(minutes=5)),
    )

    events = [
        event
        async for event in service.stream_chat_turn(
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            message="Design entity types",
        )
    ]

    assert events[-1]["ok"] is True
    assert chat_agent.last_workload_token


@pytest.mark.asyncio
async def test_stream_chat_turn_wait_when_job_package_unprepared() -> None:
    service, repo = _build_chat_turn_service(readiness=IngestionReadinessSnapshot(2, 0))

    events = [
        event
        async for event in service.stream_chat_turn(
            tenant_id="tenant-1",
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


@pytest.mark.asyncio
async def test_stream_runtime_warmup_marks_memory_backend_ready() -> None:
    service, _repo = _build_chat_turn_service(readiness=IngestionReadinessSnapshot(1, 1))

    events = [
        event
        async for event in service.stream_runtime_warmup(
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        )
    ]

    assert any(event.get("type") == "ready" for event in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["ok"] is True
    assert done.get("ready") is True


class _FailingChatAgent:
    async def stream_turn(self, **kwargs):
        yield {
            "type": "done",
            "ok": False,
            "error": {"code": "MODEL_ERROR", "message": "Vertex request failed"},
        }


class _IncompleteChatAgent:
    async def stream_turn(self, **kwargs):
        yield {"type": "thinking", "recent": ["Working…"]}


@pytest.mark.asyncio
async def test_stream_chat_turn_emits_error_when_agent_stream_incomplete() -> None:
    repo = _InMemoryAgentSessionRepository()
    sticky = InMemoryStickySessionRuntimeManager()
    session_service = ExtractionAgentSessionService(repository=repo)
    runtime_service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(
            IngestionReadinessSnapshot(1, 1)
        ),
        sticky_runtime_manager=sticky,
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_InstantHealthChecker(),
        runtime_backend="memory",
        sticky_health_timeout_seconds=5.0,
    )
    service = ExtractionChatTurnService(
        session_service=session_service,
        runtime_service=runtime_service,
        chat_agent=_IncompleteChatAgent(),
    )

    events = [
        event
        async for event in service.stream_chat_turn(
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            message="Hello!",
        )
    ]

    done = events[-1]
    assert done["type"] == "done"
    assert done["ok"] is False
    assert done["error"]["code"] == "AGENT_STREAM_INCOMPLETE"


@pytest.mark.asyncio
async def test_stream_chat_turn_persists_user_message_when_agent_fails() -> None:
    repo = _InMemoryAgentSessionRepository()
    sticky = InMemoryStickySessionRuntimeManager()
    session_service = ExtractionAgentSessionService(repository=repo)
    runtime_service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(
            IngestionReadinessSnapshot(1, 1)
        ),
        sticky_runtime_manager=sticky,
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_InstantHealthChecker(),
        runtime_backend="memory",
        sticky_health_timeout_seconds=5.0,
    )
    service = ExtractionChatTurnService(
        session_service=session_service,
        runtime_service=runtime_service,
        chat_agent=_FailingChatAgent(),
    )

    events = [
        event
        async for event in service.stream_chat_turn(
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            message="Hello!",
        )
    ]

    assert events[-1]["ok"] is False
    active = await repo.find_active_by_scope("user-1", "kg-1", ExtractionSessionMode.SCHEMA_BOOTSTRAP)
    assert active is not None
    assert active.message_history[-1] == {"role": "user", "content": "Hello!"}
