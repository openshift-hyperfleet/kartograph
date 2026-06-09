"""Application service for extraction agent session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ulid import ULID

from extraction.application.skill_resolution_service import (
    ExtractionSkillResolutionService,
)
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import BootstrapIntakePath, ExtractionSessionMode
from extraction.domain.value_objects import ExtractionSessionRunMetric
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
    ) -> None:
        self._repository = repository
        self._skill_resolution_service = skill_resolution_service
        self._run_metrics_reader = run_metrics_reader
        self._sticky_runtime_manager = sticky_runtime_manager

    @staticmethod
    def _build_bootstrap_intake_prompt() -> str:
        return (
            "Before we draft schema types, share your capabilities and goals for this "
            "knowledge graph. Then choose one path: "
            "(1) immediate first-pass schema attempt, or "
            "(2) guided question-by-question co-design."
        )

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

    async def save_session(self, session: ExtractionAgentSession) -> ExtractionAgentSession:
        """Persist session mutations after a chat turn."""
        session.updated_at = datetime.now(UTC)
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
            if self._sticky_runtime_manager is not None:
                self._sticky_runtime_manager.reset_runtime(
                    session_id=active.id,
                    user_id=user_id,
                    knowledge_graph_id=knowledge_graph_id,
                    mode=mode.value,
                )
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
            session.archive()
            await self._repository.save(session)
        return session

    async def set_bootstrap_intake_path_for_active_session(
        self,
        user_id: str,
        knowledge_graph_id: str,
        selected_path: BootstrapIntakePath,
        capabilities_goals: str | None,
    ) -> ExtractionAgentSession:
        """Persist bootstrap path selection for session continuity."""
        session = await self.get_or_create_active_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        )
        intake = dict(session.runtime_context.get("bootstrap_intake", {}))
        intake["status"] = "path_selected"
        intake["selected_path"] = selected_path.value
        intake["capabilities_goals"] = capabilities_goals
        intake["selected_at"] = datetime.now(UTC).isoformat()
        session.runtime_context["bootstrap_intake"] = intake
        session.updated_at = datetime.now(UTC)
        await self._repository.save(session)
        return session
