"""Orchestrates graph-management chat turns with sticky runtime and streaming events."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.application.job_package_gate import resolve_job_package_gate
from extraction.application.skill_resolution_service import ExtractionSkillResolutionService
from extraction.domain.value_objects import (
    ExtractionSessionMode,
    GraphManagementUiMode,
    SessionJobPackagePhase,
)
from extraction.ports.chat_agent import IExtractionChatAgent
from extraction.ports.ingestion_readiness import IIngestionReadinessReader
from extraction.ports.runtime import IStickySessionRuntimeManager
from extraction.ports.sticky_session_bootstrap import IStickySessionBootstrapBuilder


class ExtractionChatTurnService:
    """Coordinates sticky runtime, JobPackage gating, and agent execution."""

    def __init__(
        self,
        *,
        session_service: ExtractionAgentSessionService,
        skill_resolution_service: ExtractionSkillResolutionService,
        ingestion_readiness_reader: IIngestionReadinessReader,
        sticky_runtime_manager: IStickySessionRuntimeManager,
        chat_agent: IExtractionChatAgent,
        bootstrap_builder: IStickySessionBootstrapBuilder,
    ) -> None:
        self._session_service = session_service
        self._skill_resolution_service = skill_resolution_service
        self._ingestion_readiness_reader = ingestion_readiness_reader
        self._sticky_runtime_manager = sticky_runtime_manager
        self._chat_agent = chat_agent
        self._bootstrap_builder = bootstrap_builder

    async def stream_chat_turn(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
        message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        trimmed = message.strip()
        if not trimmed:
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "EMPTY_MESSAGE",
                    "message": "Message must not be empty.",
                },
            }
            return

        session = await self._session_service.get_or_create_active_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )

        resolved_skills = await self._skill_resolution_service.resolve_for_graph_management_turn(
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            ui_mode=ui_mode,
        )
        session.runtime_context["agent_configuration"] = {
            "system_prompt": resolved_skills.system_prompt,
            "prompt_hierarchy": list(resolved_skills.prompt_hierarchy),
            "guardrails": list(resolved_skills.guardrails),
            "skills": dict(resolved_skills.skills),
            "graph_management_ui_mode": ui_mode.value,
        }

        readiness = await self._ingestion_readiness_reader.read_for_knowledge_graph(
            knowledge_graph_id=knowledge_graph_id,
        )
        gate = resolve_job_package_gate(ui_mode=ui_mode, readiness=readiness)
        session.runtime_context["job_package"] = {
            "phase": gate.phase.value,
            "data_source_count": readiness.data_source_count,
            "prepared_source_count": readiness.prepared_source_count,
        }

        session.message_history.append({"role": "user", "content": trimmed})
        session.updated_at = datetime.now(UTC)

        if gate.phase == SessionJobPackagePhase.AWAITING_PREPARE:
            wait_message = gate.wait_message or "Waiting for JobPackage ingestion context."
            session.runtime_context["activity_lines"] = [wait_message]
            yield {
                "type": "wait",
                "phase": gate.phase.value,
                "message": wait_message,
            }
            yield {
                "type": "thinking",
                "recent": ["Waiting for JobPackage ingestion context…", wait_message],
            }
            assistant_reply = (
                f"**Waiting for ingestion context**\n\n{wait_message}\n\n"
                "I'll respond with full repository-aware guidance once JobPackage "
                "material is prepared for this knowledge graph."
            )
            session.message_history.append({"role": "assistant", "content": assistant_reply})
            session.updated_at = datetime.now(UTC)
            await self._session_service.save_session(session)
            yield {"type": "done", "ok": True, "reply": assistant_reply, "wait": True}
            return

        bootstrap = await self._bootstrap_builder.build(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            session_id=session.id,
            include_job_packages=gate.phase != SessionJobPackagePhase.NOT_REQUIRED,
        )
        lease = self._sticky_runtime_manager.get_or_start_runtime(
            session_id=session.id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode.value,
            bootstrap=bootstrap,
        )
        session.runtime_context["sticky_runtime"] = {
            "container_id": lease.container_id,
            "status": lease.status,
            "expires_at": lease.expires_at.isoformat(),
            "runtime_base_url": lease.runtime_base_url,
        }

        yield {
            "type": "thinking",
            "recent": [
                "Contacting Graph Management Assistant…",
                f"Sticky container {lease.container_id[:8]} active",
            ],
        }

        session.runtime_context["job_package"]["phase"] = SessionJobPackagePhase.READY.value
        thinking_lines: list[str] = []
        assistant_reply: str | None = None
        async for event in self._chat_agent.stream_turn(
            session=session,
            user_message=trimmed,
            ui_mode=ui_mode,
        ):
            if event.get("type") == "thinking":
                recent = event.get("recent")
                if isinstance(recent, list):
                    thinking_lines = [str(line) for line in recent if str(line).strip()]
                    session.runtime_context["activity_lines"] = thinking_lines
            if event.get("type") == "done":
                if event.get("ok") is True and event.get("reply"):
                    assistant_reply = str(event["reply"])
            yield event

        if assistant_reply:
            session.message_history.append({"role": "assistant", "content": assistant_reply})
            session.updated_at = datetime.now(UTC)
            session.runtime_context.pop("activity_lines", None)
            await self._session_service.save_session(session)
