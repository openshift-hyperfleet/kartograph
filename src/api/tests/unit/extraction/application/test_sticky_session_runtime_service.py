"""Unit tests for StickySessionRuntimeService."""

from __future__ import annotations

import pytest

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.application.sticky_session_runtime_service import StickySessionRuntimeService
from extraction.domain.value_objects import (
    ExtractionSessionMode,
    GraphManagementUiMode,
    IngestionReadinessSnapshot,
)
from extraction.infrastructure.workload_runtime import InMemoryStickySessionRuntimeManager
from shared_kernel.container_runtime.ports import ContainerRuntimeError


class _InMemoryAgentSessionRepository:
    def __init__(self) -> None:
        self._sessions = {}

    async def save(self, session) -> None:
        from dataclasses import replace

        self._sessions[session.id] = replace(session)

    async def get_by_id(self, session_id: str):
        session = self._sessions.get(session_id)
        if session is None:
            return None
        from dataclasses import replace

        return replace(session)

    async def find_active_by_scope(self, user_id: str, knowledge_graph_id: str, mode):
        for session in self._sessions.values():
            if (
                session.user_id == user_id
                and session.knowledge_graph_id == knowledge_graph_id
                and session.mode == mode
                and session.archived_at is None
            ):
                from dataclasses import replace

                return replace(session)
        return None

    async def list_by_scope(self, user_id: str, knowledge_graph_id: str, mode=None):
        return []


class _StaticSkillResolutionService:
    async def resolve_for_graph_management_turn(self, **kwargs):
        return type(
            "_Resolved",
            (),
            {
                "system_prompt": "system",
                "prompt_hierarchy": ("platform",),
                "guardrails": ("scope",),
                "skills": {},
            },
        )()


class _StaticIngestionReadinessReader:
    async def read_for_knowledge_graph(self, *, knowledge_graph_id: str):
        return IngestionReadinessSnapshot(0, 0)


class _StaticBootstrapBuilder:
    async def build(self, **kwargs):
        return None


class _InstantHealthChecker:
    async def wait_until_healthy(self, **kwargs):
        return
        yield  # pragma: no cover


class _FailingStickyRuntimeManager(InMemoryStickySessionRuntimeManager):
    def get_or_start_runtime(self, **kwargs):
        raise ContainerRuntimeError("docker run failed: image not found")


@pytest.mark.asyncio
async def test_stream_runtime_warmup_surfaces_container_start_failure() -> None:
    repo = _InMemoryAgentSessionRepository()
    session_service = ExtractionAgentSessionService(repository=repo)
    service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(),
        sticky_runtime_manager=_FailingStickyRuntimeManager(),
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_InstantHealthChecker(),
        runtime_backend="container",
        sticky_health_timeout_seconds=5.0,
    )

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

    done = events[-1]
    assert done["type"] == "done"
    assert done["ok"] is False
    assert done["error"]["code"] == "RUNTIME_START_FAILED"
    assert "image not found" in done["error"]["message"]


class _OnceInactiveStickyRuntimeManager(InMemoryStickySessionRuntimeManager):
    def __init__(self) -> None:
        super().__init__()
        self._checked = False

    def try_resolve_active_lease(self, **kwargs):
        if not self._checked:
            self._checked = True
            return None
        return super().try_resolve_active_lease(**kwargs)


@pytest.mark.asyncio
async def test_ensure_runtime_for_chat_reprepares_when_persisted_runtime_is_inactive() -> None:
    repo = _InMemoryAgentSessionRepository()
    session_service = ExtractionAgentSessionService(repository=repo)
    sticky = _OnceInactiveStickyRuntimeManager()
    service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(),
        sticky_runtime_manager=sticky,
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_InstantHealthChecker(),
        runtime_backend="memory",
        sticky_health_timeout_seconds=5.0,
    )
    session = await session_service.get_or_create_active_session(
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
    )
    session.runtime_context["sticky_runtime"] = {
        "container_id": "dead-container",
        "status": "active",
        "runtime_base_url": "memory://sticky-runtime",
        "phase": "ready",
    }
    await session_service.save_session(session)

    events = [
        event
        async for event in service.ensure_runtime_for_chat(
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            session=session,
        )
    ]

    assert any(event.get("type") == "ready" for event in events)
    assert session.runtime_context["sticky_runtime"]["container_id"] != "dead-container"
    assert sticky.try_resolve_active_lease(session_id=session.id) is not None


@pytest.mark.asyncio
async def test_ensure_runtime_for_chat_reuses_running_container_without_reprepare() -> None:
    repo = _InMemoryAgentSessionRepository()
    session_service = ExtractionAgentSessionService(repository=repo)
    sticky = InMemoryStickySessionRuntimeManager()
    service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(),
        sticky_runtime_manager=sticky,
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_InstantHealthChecker(),
        runtime_backend="memory",
        sticky_health_timeout_seconds=5.0,
    )
    session = await session_service.get_or_create_active_session(
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
    )
    sticky.get_or_start_runtime(
        session_id=session.id,
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP.value,
    )

    events = [
        event
        async for event in service.ensure_runtime_for_chat(
            tenant_id="tenant-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
            session=session,
        )
    ]

    assert events == []
    assert session.runtime_context["sticky_runtime"]["phase"] == "ready"
