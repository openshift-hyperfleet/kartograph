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

    async def find_active_by_ui_mode(self, user_id: str, knowledge_graph_id: str, ui_mode):
        for session in self._sessions.values():
            if (
                session.user_id == user_id
                and session.knowledge_graph_id == knowledge_graph_id
                and session.graph_management_ui_mode == ui_mode
                and session.archived_at is None
            ):
                from dataclasses import replace

                return replace(session)
        return None

    async def list_active_by_user_and_kg(self, user_id: str, knowledge_graph_id: str):
        from dataclasses import replace

        return [
            replace(session)
            for session in self._sessions.values()
            if session.user_id == user_id
            and session.knowledge_graph_id == knowledge_graph_id
            and session.archived_at is None
        ]

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
    async def resolve_job_packages(self, **kwargs):
        return ()

    async def build(self, **kwargs):
        return None


class _RecordingBootstrapBuilder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def resolve_job_packages(self, **kwargs):
        from extraction.domain.prepared_job_package_source import PreparedJobPackageSource

        return (
            PreparedJobPackageSource(
                package_id="pkg-1",
                data_source_id="ds-1",
                data_source_name="hyperfleet-api",
                repository_folder="hyperfleet-api",
            ),
        )

    async def build(self, **kwargs):
        self.calls.append(kwargs)
        return None


class _PreparedIngestionReadinessReader:
    async def read_for_knowledge_graph(self, *, knowledge_graph_id: str):
        return IngestionReadinessSnapshot(data_source_count=1, prepared_source_count=1)


class _InstantHealthChecker:
    async def wait_until_healthy(self, **kwargs):
        return
        yield  # pragma: no cover

    async def is_healthy(self, **kwargs) -> bool:
        return True


class _UnhealthyHealthChecker:
    async def wait_until_healthy(self, **kwargs):
        return
        yield  # pragma: no cover

    async def is_healthy(self, **kwargs) -> bool:
        return False


class _FailingStickyRuntimeManager(InMemoryStickySessionRuntimeManager):
    def get_or_start_runtime(self, **kwargs):
        raise ContainerRuntimeError("docker run failed: image not found")


@pytest.mark.asyncio
async def test_stream_runtime_warmup_surfaces_container_start_failure() -> None:
    repo = _InMemoryAgentSessionRepository()
    session_service = ExtractionAgentSessionService(repository=repo)
    await session_service.start_session(
        user_id="user-1",
        knowledge_graph_id="kg-1",
        ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
    )
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
    session = await session_service.start_session(
        user_id="user-1",
        knowledge_graph_id="kg-1",
        ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
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


@pytest.mark.asyncio
async def test_ensure_runtime_for_chat_restarts_when_job_package_materialization_changes() -> None:
    repo = _InMemoryAgentSessionRepository()
    session_service = ExtractionAgentSessionService(repository=repo)
    sticky = InMemoryStickySessionRuntimeManager()
    bootstrap = _RecordingBootstrapBuilder()
    service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_PreparedIngestionReadinessReader(),
        sticky_runtime_manager=sticky,
        bootstrap_builder=bootstrap,
        health_checker=_InstantHealthChecker(),
        runtime_backend="container",
        sticky_health_timeout_seconds=5.0,
    )
    session = await session_service.start_session(
        user_id="user-1",
        knowledge_graph_id="kg-1",
        ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
    )
    sticky.get_or_start_runtime(
        session_id=session.id,
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP.value,
    )
    lease = sticky.try_resolve_active_lease(session_id=session.id)
    session.runtime_context["workspace_materialization"] = {"job_package_ids": ["stale-pkg"]}
    session.runtime_context["sticky_runtime"] = {
        "container_id": lease.container_id,
        "status": "active",
        "runtime_base_url": lease.runtime_base_url,
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
    assert bootstrap.calls


@pytest.mark.asyncio
async def test_ensure_runtime_for_chat_reuses_running_container_without_reprepare() -> None:
    repo = _InMemoryAgentSessionRepository()
    session_service = ExtractionAgentSessionService(repository=repo)
    sticky = InMemoryStickySessionRuntimeManager()
    bootstrap = _RecordingBootstrapBuilder()
    service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_PreparedIngestionReadinessReader(),
        sticky_runtime_manager=sticky,
        bootstrap_builder=bootstrap,
        health_checker=_InstantHealthChecker(),
        runtime_backend="container",
        sticky_health_timeout_seconds=5.0,
    )
    session = await session_service.start_session(
        user_id="user-1",
        knowledge_graph_id="kg-1",
        ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
    )
    sticky.get_or_start_runtime(
        session_id=session.id,
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP.value,
    )
    session.runtime_context["workspace_materialization"] = {"job_package_ids": ["pkg-1"]}
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

    assert events == []
    assert session.runtime_context["sticky_runtime"]["phase"] == "ready"
    assert bootstrap.calls == []


@pytest.mark.asyncio
async def test_ensure_runtime_for_chat_restarts_when_persisted_container_is_unhealthy() -> None:
    repo = _InMemoryAgentSessionRepository()
    session_service = ExtractionAgentSessionService(repository=repo)
    sticky = InMemoryStickySessionRuntimeManager()
    service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=_StaticSkillResolutionService(),
        ingestion_readiness_reader=_StaticIngestionReadinessReader(),
        sticky_runtime_manager=sticky,
        bootstrap_builder=_StaticBootstrapBuilder(),
        health_checker=_UnhealthyHealthChecker(),
        runtime_backend="memory",
        sticky_health_timeout_seconds=5.0,
    )
    session = await session_service.start_session(
        user_id="user-1",
        knowledge_graph_id="kg-1",
        ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
    )
    sticky.get_or_start_runtime(
        session_id=session.id,
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP.value,
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
