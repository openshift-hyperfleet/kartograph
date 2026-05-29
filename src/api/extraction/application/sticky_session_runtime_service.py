"""Prepare sticky session containers before graph-management chat turns."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.application.job_package_gate import resolve_job_package_gate
from extraction.application.skill_resolution_service import ExtractionSkillResolutionService
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import (
    ExtractionSessionMode,
    GraphManagementUiMode,
    SessionJobPackagePhase,
)
from extraction.ports.ingestion_readiness import IIngestionReadinessReader
from extraction.ports.runtime import IStickySessionRuntimeManager, StickySessionRuntimeLease
from extraction.ports.sticky_runtime_health import IStickyRuntimeHealthChecker
from extraction.ports.sticky_session_bootstrap import IStickySessionBootstrapBuilder


class StickySessionRuntimeService:
    """Starts sticky containers and streams transparent readiness progress."""

    def __init__(
        self,
        *,
        session_service: ExtractionAgentSessionService,
        skill_resolution_service: ExtractionSkillResolutionService,
        ingestion_readiness_reader: IIngestionReadinessReader,
        sticky_runtime_manager: IStickySessionRuntimeManager,
        bootstrap_builder: IStickySessionBootstrapBuilder,
        health_checker: IStickyRuntimeHealthChecker,
        runtime_backend: str,
        sticky_health_timeout_seconds: float,
    ) -> None:
        self._session_service = session_service
        self._skill_resolution_service = skill_resolution_service
        self._ingestion_readiness_reader = ingestion_readiness_reader
        self._sticky_runtime_manager = sticky_runtime_manager
        self._bootstrap_builder = bootstrap_builder
        self._health_checker = health_checker
        self._runtime_backend = runtime_backend
        self._sticky_health_timeout_seconds = sticky_health_timeout_seconds

    async def stream_runtime_warmup(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
    ) -> AsyncIterator[dict[str, Any]]:
        session = await self._session_service.get_or_create_active_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
        )
        async for event in self._stream_prepare_runtime(
            tenant_id=tenant_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            ui_mode=ui_mode,
            session=session,
            persist_session=True,
            emit_terminal=True,
        ):
            yield event

    async def ensure_runtime_for_chat(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
        session: ExtractionAgentSession,
    ) -> AsyncIterator[dict[str, Any]]:
        sticky = session.runtime_context.get("sticky_runtime", {})
        if (
            isinstance(sticky.get("runtime_base_url"), str)
            and sticky.get("phase") == "ready"
            and sticky.get("container_id")
        ):
            return
        async for event in self._stream_prepare_runtime(
            tenant_id=tenant_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            ui_mode=ui_mode,
            session=session,
            persist_session=True,
            emit_terminal=False,
        ):
            yield event

    async def _stream_prepare_runtime(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
        session: ExtractionAgentSession,
        persist_session: bool,
        emit_terminal: bool,
    ) -> AsyncIterator[dict[str, Any]]:
        yield {
            "type": "thinking",
            "recent": ["Preparing Graph Management Assistant runtime…"],
        }

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

        if gate.phase == SessionJobPackagePhase.AWAITING_PREPARE:
            wait_message = gate.wait_message or "Waiting for JobPackage ingestion context."
            session.runtime_context["activity_lines"] = [wait_message]
            session.runtime_context["sticky_runtime"] = {
                "phase": "awaiting_job_package",
                "status": "waiting",
            }
            if persist_session:
                await self._session_service.save_session(session)
            yield {"type": "wait", "phase": gate.phase.value, "message": wait_message}
            yield {
                "type": "thinking",
                "recent": ["Waiting for JobPackage ingestion context…", wait_message],
            }
            if emit_terminal:
                yield {
                    "type": "done",
                    "ok": True,
                    "ready": False,
                    "wait": True,
                    "message": wait_message,
                }
            return

        if self._runtime_backend != "container":
            lease = self._sticky_runtime_manager.get_or_start_runtime(
                session_id=session.id,
                user_id=user_id,
                knowledge_graph_id=knowledge_graph_id,
                mode=mode.value,
                bootstrap=None,
            )
            session.runtime_context["sticky_runtime"] = self._lease_context(lease, phase="ready")
            if persist_session:
                await self._session_service.save_session(session)
            yield {
                "type": "thinking",
                "recent": ["In-memory assistant runtime ready"],
            }
            yield {"type": "ready", "runtime_base_url": lease.runtime_base_url}
            yield {"type": "done", "ok": True, "ready": True}
            return

        yield {
            "type": "thinking",
            "recent": [
                "Preparing Graph Management Assistant runtime…",
                "Materializing workspace and skills for sticky container",
            ],
        }
        bootstrap = await self._bootstrap_builder.build(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            session_id=session.id,
            include_job_packages=gate.phase != SessionJobPackagePhase.NOT_REQUIRED,
        )
        yield {
            "type": "thinking",
            "recent": [
                "Materializing workspace and skills for sticky container",
                "Starting isolated Claude Agent SDK container",
            ],
        }
        lease = self._sticky_runtime_manager.get_or_start_runtime(
            session_id=session.id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode.value,
            bootstrap=bootstrap,
        )
        session.runtime_context["sticky_runtime"] = self._lease_context(lease, phase="starting")
        yield {
            "type": "thinking",
            "recent": [
                "Starting isolated Claude Agent SDK container",
                f"Container {lease.container_id[:8]} launched",
            ],
        }

        runtime_base_url = lease.runtime_base_url or ""
        try:
            async for line in self._health_checker.wait_until_healthy(
                runtime_base_url=runtime_base_url,
                timeout_seconds=self._sticky_health_timeout_seconds,
            ):
                yield {"type": "thinking", "recent": [line]}
        except TimeoutError as exc:
            session.runtime_context["sticky_runtime"]["phase"] = "unhealthy"
            session.runtime_context["sticky_runtime"]["status"] = "unhealthy"
            if persist_session:
                await self._session_service.save_session(session)
            yield {
                "type": "done",
                "ok": False,
                "ready": False,
                "error": {"code": "RUNTIME_UNHEALTHY", "message": str(exc)},
            }
            return

        session.runtime_context["sticky_runtime"] = self._lease_context(lease, phase="ready")
        session.runtime_context.pop("activity_lines", None)
        session.updated_at = datetime.now(UTC)
        if persist_session:
            await self._session_service.save_session(session)

        yield {"type": "ready", "runtime_base_url": runtime_base_url}
        yield {"type": "done", "ok": True, "ready": True}

    @staticmethod
    def _lease_context(lease: StickySessionRuntimeLease, *, phase: str) -> dict[str, Any]:
        return {
            "container_id": lease.container_id,
            "status": lease.status,
            "expires_at": lease.expires_at.isoformat(),
            "runtime_base_url": lease.runtime_base_url,
            "phase": phase,
        }
