"""Application service for extraction agent session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ulid import ULID

from extraction.application.graph_management_session_journal import (
    GraphManagementSessionJournalService,
)
from extraction.application.skill_resolution_service import (
    ExtractionSkillResolutionService,
)
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.graph_management_session_scope import resolve_backend_session_mode
from extraction.domain.value_objects import (
    BootstrapIntakePath,
    ExtractionSessionMode,
    ExtractionSessionRunMetric,
    GraphManagementUiMode,
)
from extraction.ports.repositories import (
    IExtractionAgentSessionRepository,
    IExtractionSessionRunMetricsReader,
)
from extraction.ports.runtime import IStickySessionRuntimeManager


@dataclass(frozen=True)
class ExtractionSessionHistoryRecord:
    """Session history entry with linked run-level metrics."""

    session: ExtractionAgentSession
    run_metrics: list[ExtractionSessionRunMetric]


class ExtractionAgentSessionService:
    """Orchestrates session create/get/list/archive behaviors by scope."""

    def __init__(
        self,
        repository: IExtractionAgentSessionRepository,
        skill_resolution_service: ExtractionSkillResolutionService | None = None,
        run_metrics_reader: IExtractionSessionRunMetricsReader | None = None,
        sticky_runtime_manager: IStickySessionRuntimeManager | None = None,
        session_journal_service: GraphManagementSessionJournalService | None = None,
        idle_session_ttl: timedelta = timedelta(hours=1),
    ) -> None:
        self._repository = repository
        self._skill_resolution_service = skill_resolution_service
        self._run_metrics_reader = run_metrics_reader
        self._sticky_runtime_manager = sticky_runtime_manager
        self._session_journal_service = session_journal_service
        self._idle_session_ttl = idle_session_ttl

    @staticmethod
    def _build_bootstrap_intake_prompt() -> str:
        return (
            "Before we draft schema types, share your capabilities and goals for this "
            "knowledge graph. Then choose one path: "
            "(1) immediate first-pass schema attempt, or "
            "(2) guided question-by-question co-design."
        )

    async def _expire_idle_sessions(self, user_id: str, knowledge_graph_id: str) -> None:
        now = datetime.now(UTC)
        if self._sticky_runtime_manager is not None:
            self._sticky_runtime_manager.cleanup_expired(now=now)

        active_sessions = await self._repository.list_active_by_user_and_kg(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        for session in active_sessions:
            if session.updated_at + self._idle_session_ttl <= now:
                await self._end_session_record(session)

    async def _terminate_sticky_runtime(self, session: ExtractionAgentSession) -> None:
        if self._sticky_runtime_manager is None:
            return
        self._sticky_runtime_manager.terminate_runtime(
            session_id=session.id,
            user_id=session.user_id,
            knowledge_graph_id=session.knowledge_graph_id,
            mode=session.mode.value,
        )

    async def _end_session_record(self, session: ExtractionAgentSession) -> None:
        if not session.is_active:
            return
        await self._terminate_sticky_runtime(session)
        if self._session_journal_service is not None:
            await self._session_journal_service.archive_session_mutations(session)
        session.archive()
        await self._repository.save(session)

    @staticmethod
    def _session_had_sticky_runtime_attempt(session: ExtractionAgentSession) -> bool:
        sticky = session.runtime_context.get("sticky_runtime")
        if not isinstance(sticky, dict):
            return False
        phase = sticky.get("phase")
        return phase in {"starting", "ready", "unhealthy", "failed"}

    async def _reconcile_orphaned_sticky_session(
        self,
        session: ExtractionAgentSession,
    ) -> ExtractionAgentSession | None:
        """Archive sessions whose sticky runtime no longer exists (e.g. after sandbox delete)."""
        if self._sticky_runtime_manager is None:
            return session
        if not self._session_had_sticky_runtime_attempt(session):
            return session

        sticky = session.runtime_context.get("sticky_runtime", {})
        container_id = sticky.get("container_id") if isinstance(sticky, dict) else None
        if self._sticky_runtime_manager.is_runtime_active(
            session_id=session.id,
            container_id=container_id if isinstance(container_id, str) else None,
            user_id=session.user_id,
            knowledge_graph_id=session.knowledge_graph_id,
            mode=session.mode.value,
        ):
            return session

        await self._end_session_record(session)
        return None

    async def _create_session(
        self,
        *,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession:
        mode = resolve_backend_session_mode(ui_mode)
        session = ExtractionAgentSession(
            id=str(ULID()),
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            graph_management_ui_mode=ui_mode,
        )
        session.runtime_context["graph_management_ui_mode"] = ui_mode.value
        if self._skill_resolution_service is not None:
            resolved = await self._skill_resolution_service.resolve_for_graph_management_turn(
                knowledge_graph_id=knowledge_graph_id,
                mode=mode,
                ui_mode=ui_mode,
            )
            session.runtime_context["agent_configuration"] = {
                "system_prompt": resolved.system_prompt,
                "prompt_hierarchy": list(resolved.prompt_hierarchy),
                "guardrails": list(resolved.guardrails),
                "skills": dict(resolved.skills),
            }
        if mode == ExtractionSessionMode.SCHEMA_BOOTSTRAP:
            session.message_history.append(
                {"role": "assistant", "content": self._build_bootstrap_intake_prompt()}
            )
            session.runtime_context["bootstrap_intake"] = {
                "status": "awaiting_path_selection",
                "selected_path": None,
                "capabilities_goals": None,
                "path_options": [
                    BootstrapIntakePath.FIRST_PASS_SCHEMA_ATTEMPT.value,
                    BootstrapIntakePath.GUIDED_CO_DESIGN.value,
                ],
            }
        await self._repository.save(session)
        return session

    async def get_active_session(
        self,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession | None:
        await self._expire_idle_sessions(user_id, knowledge_graph_id)
        session = await self._repository.find_active_by_ui_mode(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=ui_mode,
        )
        if session is None:
            return None
        return await self._reconcile_orphaned_sticky_session(session)

    async def start_session(
        self,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession:
        await self._expire_idle_sessions(user_id, knowledge_graph_id)
        existing = await self._repository.find_active_by_ui_mode(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=ui_mode,
        )
        if existing is not None:
            existing = await self._reconcile_orphaned_sticky_session(existing)
            if existing is not None:
                return existing
        return await self._create_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=ui_mode,
        )

    async def end_session(
        self,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession | None:
        await self._expire_idle_sessions(user_id, knowledge_graph_id)
        active = await self._repository.find_active_by_ui_mode(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=ui_mode,
        )
        if active is None:
            return None
        await self._end_session_record(active)
        return active

    async def get_or_create_active_session(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode | None = None,
    ) -> ExtractionAgentSession:
        """Return active session for UI mode or create one (legacy chat auto-start)."""
        resolved_ui_mode = ui_mode or (
            GraphManagementUiMode.INITIAL_SCHEMA_DESIGN
            if mode == ExtractionSessionMode.SCHEMA_BOOTSTRAP
            else GraphManagementUiMode.EXTRACTION_JOBS
        )
        if resolve_backend_session_mode(resolved_ui_mode) != mode:
            raise ValueError("graph_management_ui_mode does not match session mode")
        existing = await self.get_active_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=resolved_ui_mode,
        )
        if existing is not None:
            return existing
        return await self.start_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=resolved_ui_mode,
        )

    async def save_session(self, session: ExtractionAgentSession) -> ExtractionAgentSession:
        """Persist session mutations after a chat turn."""
        session.updated_at = datetime.now(UTC)
        await self._repository.save(session)
        return session

    async def clear_chat(
        self,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession:
        await self.end_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=ui_mode,
        )
        return await self.start_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=ui_mode,
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

    async def list_session_history(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> list[ExtractionSessionHistoryRecord]:
        sessions = await self._repository.list_by_scope(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )
        if not sessions:
            return []

        metrics_by_session: dict[str, list[ExtractionSessionRunMetric]] = {}
        if self._run_metrics_reader is not None:
            metrics_by_session = await self._run_metrics_reader.find_metrics_by_session_ids(
                knowledge_graph_id=knowledge_graph_id,
                session_ids=[session.id for session in sessions],
            )

        return [
            ExtractionSessionHistoryRecord(
                session=session,
                run_metrics=metrics_by_session.get(session.id, []),
            )
            for session in sessions
        ]

    async def archive_session(self, session_id: str) -> ExtractionAgentSession | None:
        session = await self._repository.get_by_id(session_id)
        if session is None:
            return None
        if session.is_active:
            await self._end_session_record(session)
        return session

    async def set_bootstrap_intake_path_for_active_session(
        self,
        user_id: str,
        knowledge_graph_id: str,
        selected_path: BootstrapIntakePath,
        capabilities_goals: str | None,
    ) -> ExtractionAgentSession:
        """Persist bootstrap path selection for session continuity."""
        session = await self.get_active_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
        )
        if session is None:
            raise ValueError("No active initial schema design session")
        intake = dict(session.runtime_context.get("bootstrap_intake", {}))
        intake["status"] = "path_selected"
        intake["selected_path"] = selected_path.value
        intake["capabilities_goals"] = capabilities_goals
        intake["selected_at"] = datetime.now(UTC).isoformat()
        session.runtime_context["bootstrap_intake"] = intake
        session.updated_at = datetime.now(UTC)
        await self._repository.save(session)
        return session
