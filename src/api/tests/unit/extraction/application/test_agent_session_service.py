"""Unit tests for ExtractionAgentSessionService."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.application.graph_management_session_journal import (
    GraphManagementSessionJournalService,
    append_applied_jsonl_to_session,
)
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.graph_management_session_scope import resolve_backend_session_mode
from extraction.domain.value_objects import (
    BootstrapIntakePath,
    ExtractionSessionMode,
    GraphManagementUiMode,
)
from extraction.infrastructure.workload_runtime import InMemoryStickySessionRuntimeManager


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

    async def find_active_by_ui_mode(
        self,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession | None:
        for session in self._by_id.values():
            if (
                session.user_id == user_id
                and session.knowledge_graph_id == knowledge_graph_id
                and session.graph_management_ui_mode == ui_mode
                and session.archived_at is None
            ):
                return replace(session)
        return None

    async def list_active_by_user_and_kg(
        self,
        user_id: str,
        knowledge_graph_id: str,
    ) -> list[ExtractionAgentSession]:
        return [
            replace(session)
            for session in self._by_id.values()
            if session.user_id == user_id
            and session.knowledge_graph_id == knowledge_graph_id
            and session.archived_at is None
        ]

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


class _InMemoryJobRepository:
    def __init__(self) -> None:
        self.inserted = []

    async def insert_archived_session_job(self, job) -> None:
        self.inserted.append(job)


class _StaticSkillResolutionService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ExtractionSessionMode, GraphManagementUiMode]] = []

    async def resolve_for_graph_management_turn(
        self,
        *,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
    ):
        self.calls.append((knowledge_graph_id, mode, ui_mode))
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
    async def test_start_session_reuses_active_for_same_ui_mode(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        first = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        )
        second = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        )

        assert first.id == second.id

    async def test_scope_isolated_by_user(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        first = await service.start_session(
            user_id="alice",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        second = await service.start_session(
            user_id="bob",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        assert first.id != second.id

    async def test_scope_isolated_by_ui_mode(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        bootstrap = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        )
        extraction_jobs = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        one_off = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.ONE_OFF_MUTATIONS,
        )

        assert len({bootstrap.id, extraction_jobs.id, one_off.id}) == 3
        assert bootstrap.mode == ExtractionSessionMode.SCHEMA_BOOTSTRAP
        assert extraction_jobs.mode == ExtractionSessionMode.EXTRACTION_OPERATIONS
        assert one_off.mode == ExtractionSessionMode.EXTRACTION_OPERATIONS

    async def test_get_active_session_returns_none_when_not_started(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        active = await service.get_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.ONE_OFF_MUTATIONS,
        )

        assert active is None

    async def test_clear_chat_archives_old_session_and_creates_new_one(self):
        repo = _InMemoryAgentSessionRepository()
        sticky = InMemoryStickySessionRuntimeManager()
        service = ExtractionAgentSessionService(
            repository=repo,
            sticky_runtime_manager=sticky,
        )

        old_session = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        old_session.message_history = [{"role": "user", "content": "hello"}]
        old_session.runtime_context = {"draft": "x"}
        old_session.updated_at = datetime.now(UTC)
        await repo.save(old_session)

        new_session = await service.clear_chat(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        archived = await repo.get_by_id(old_session.id)
        assert archived is not None
        assert archived.archived_at is not None
        assert new_session.id != old_session.id
        assert new_session.message_history == []
        assert new_session.runtime_context.get("graph_management_ui_mode") == (
            GraphManagementUiMode.EXTRACTION_JOBS.value
        )

    async def test_end_session_archives_writes_to_graph_history(self):
        repo = _InMemoryAgentSessionRepository()
        job_repo = _InMemoryJobRepository()
        journal = GraphManagementSessionJournalService(
            session_repository=repo,
            extraction_job_repository=job_repo,
        )
        sticky = InMemoryStickySessionRuntimeManager()
        service = ExtractionAgentSessionService(
            repository=repo,
            sticky_runtime_manager=sticky,
            session_journal_service=journal,
        )

        session = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.ONE_OFF_MUTATIONS,
        )
        append_applied_jsonl_to_session(
            session,
            applied_jsonl=(
                '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service",'
                '"set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap"}}'
            ),
        )
        await repo.save(session)

        ended = await service.end_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.ONE_OFF_MUTATIONS,
        )

        assert ended is not None
        assert ended.archived_at is not None
        assert len(job_repo.inserted) == 1

    async def test_end_session_skips_graph_history_when_no_writes(self):
        repo = _InMemoryAgentSessionRepository()
        job_repo = _InMemoryJobRepository()
        journal = GraphManagementSessionJournalService(
            session_repository=repo,
            extraction_job_repository=job_repo,
        )
        service = ExtractionAgentSessionService(
            repository=repo,
            session_journal_service=journal,
        )

        await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        await service.end_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        assert job_repo.inserted == []

    async def test_idle_sessions_auto_end_after_one_hour(self):
        repo = _InMemoryAgentSessionRepository()
        sticky = InMemoryStickySessionRuntimeManager()
        service = ExtractionAgentSessionService(
            repository=repo,
            sticky_runtime_manager=sticky,
            idle_session_ttl=timedelta(hours=1),
        )

        session = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        session.updated_at = datetime.now(UTC) - timedelta(hours=2)
        await repo.save(session)

        active = await service.get_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        assert active is None
        archived = await repo.get_by_id(session.id)
        assert archived is not None
        assert archived.archived_at is not None

    async def test_list_sessions_includes_archived_history(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        first = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        await service.clear_chat(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
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

        session = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        )

        assert "agent_configuration" in session.runtime_context
        config = session.runtime_context["agent_configuration"]
        assert config["system_prompt"] == "Bootstrap system prompt"
        assert config["skills"]["schema_modeling"] == "bootstrap schema guidance"
        assert skill_resolution.calls == [
            ("kg-1", ExtractionSessionMode.SCHEMA_BOOTSTRAP, GraphManagementUiMode.INITIAL_SCHEMA_DESIGN)
        ]

    async def test_bootstrap_session_seeds_capabilities_intake_prompt_state(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)

        session = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        )

        assert session.message_history
        assert session.message_history[0]["role"] == "assistant"
        assert "capabilities" in session.message_history[0]["content"].lower()
        intake = session.runtime_context["bootstrap_intake"]
        assert intake["status"] == "awaiting_path_selection"
        assert intake["selected_path"] is None

    async def test_select_bootstrap_intake_path_persists_choice_for_continuity(self):
        repo = _InMemoryAgentSessionRepository()
        service = ExtractionAgentSessionService(repository=repo)
        session = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        )

        updated = await service.set_bootstrap_intake_path_for_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            selected_path=BootstrapIntakePath.GUIDED_CO_DESIGN,
            capabilities_goals="I can provide domain terms but need guidance.",
        )

        intake = updated.runtime_context["bootstrap_intake"]
        assert intake["selected_path"] == BootstrapIntakePath.GUIDED_CO_DESIGN.value
        assert intake["status"] == "path_selected"
        assert intake["capabilities_goals"] == "I can provide domain terms but need guidance."
        assert updated.id == session.id


class _InactiveStickyRuntimeManager(InMemoryStickySessionRuntimeManager):
    def is_runtime_active(self, **kwargs) -> bool:
        return False


@pytest.mark.asyncio
class TestOrphanedStickySessionReconciliation:
    async def test_get_active_session_archives_session_when_runtime_is_gone(self):
        repo = _InMemoryAgentSessionRepository()
        runtime = _InactiveStickyRuntimeManager()
        service = ExtractionAgentSessionService(
            repository=repo,
            sticky_runtime_manager=runtime,
        )
        session = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        session.runtime_context["sticky_runtime"] = {
            "phase": "ready",
            "status": "active",
            "container_id": "kartograph-gma-deadbeef",
        }
        await repo.save(session)

        active = await service.get_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        assert active is None
        stored = await repo.get_by_id(session.id)
        assert stored is not None
        assert stored.archived_at is not None

    async def test_get_active_session_keeps_session_without_runtime_attempt(self):
        repo = _InMemoryAgentSessionRepository()
        runtime = _InactiveStickyRuntimeManager()
        service = ExtractionAgentSessionService(
            repository=repo,
            sticky_runtime_manager=runtime,
        )
        session = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        active = await service.get_active_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        assert active is not None
        assert active.id == session.id


def test_resolve_backend_session_mode_maps_ui_modes() -> None:
    assert resolve_backend_session_mode(GraphManagementUiMode.INITIAL_SCHEMA_DESIGN) == (
        ExtractionSessionMode.SCHEMA_BOOTSTRAP
    )
    assert resolve_backend_session_mode(GraphManagementUiMode.EXTRACTION_JOBS) == (
        ExtractionSessionMode.EXTRACTION_OPERATIONS
    )
    assert resolve_backend_session_mode(GraphManagementUiMode.ONE_OFF_MUTATIONS) == (
        ExtractionSessionMode.EXTRACTION_OPERATIONS
    )
