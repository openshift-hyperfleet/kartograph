"""Prepare sticky session containers before graph-management chat turns."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.application.job_package_gate import resolve_job_package_gate
from extraction.application.sticky_session_materialization import should_materialize_job_packages
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
from shared_kernel.container_runtime.ports import ContainerRuntimeError

from extraction.application.thinking_activity import thinking_event

NDJSON_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


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
        container_id = sticky.get("container_id")
        persisted_container_id = container_id if isinstance(container_id, str) else None

        lease = await asyncio.to_thread(
            self._sticky_runtime_manager.try_resolve_active_lease,
            session_id=session.id,
            container_id=persisted_container_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode.value,
        )
        if lease is not None:
            runtime_base_url = lease.runtime_base_url or ""
            readiness = await self._ingestion_readiness_reader.read_for_knowledge_graph(
                knowledge_graph_id=knowledge_graph_id,
            )
            gate = resolve_job_package_gate(ui_mode=ui_mode, readiness=readiness)
            include_job_packages = should_materialize_job_packages(
                readiness=readiness,
                gate=gate,
            )
            expected_packages = await self._bootstrap_builder.resolve_job_packages(
                knowledge_graph_id=knowledge_graph_id,
                include_job_packages=include_job_packages,
            )
            stored_materialization = session.runtime_context.get("workspace_materialization", {})
            stored_package_ids = tuple(stored_materialization.get("job_package_ids") or ())
            expected_package_ids = tuple(source.package_id for source in expected_packages)
            if (
                await self._health_checker.is_healthy(runtime_base_url=runtime_base_url)
                and stored_package_ids == expected_package_ids
            ):
                session.runtime_context["sticky_runtime"] = self._lease_context(
                    lease, phase="ready"
                )
                await self._session_service.save_session(session)
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
        recent: list[str] = []
        recent, event = thinking_event(recent, "Preparing Graph Management Assistant runtime…")
        yield event

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
            recent, event = thinking_event(recent, "Waiting for JobPackage ingestion context…")
            yield event
            recent, event = thinking_event(recent, wait_message)
            yield event
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
            lease = await asyncio.to_thread(
                self._sticky_runtime_manager.get_or_start_runtime,
                session_id=session.id,
                user_id=user_id,
                knowledge_graph_id=knowledge_graph_id,
                mode=mode.value,
                bootstrap=None,
            )
            session.runtime_context["sticky_runtime"] = self._lease_context(lease, phase="ready")
            if persist_session:
                await self._session_service.save_session(session)
            recent, event = thinking_event(recent, "In-memory assistant runtime ready")
            yield event
            yield {"type": "ready", "runtime_base_url": lease.runtime_base_url}
            yield {"type": "done", "ok": True, "ready": True}
            return

        recent, event = thinking_event(
            recent,
            "Materializing workspace and skills for sticky container",
        )
        yield event
        include_job_packages = should_materialize_job_packages(
            readiness=readiness,
            gate=gate,
        )
        job_packages = await self._bootstrap_builder.resolve_job_packages(
            knowledge_graph_id=knowledge_graph_id,
            include_job_packages=include_job_packages,
        )
        bootstrap = await self._bootstrap_builder.build(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            session_id=session.id,
            include_job_packages=include_job_packages,
        )
        session.runtime_context["workspace_materialization"] = {
            "job_package_ids": [source.package_id for source in job_packages],
            "repository_folders": [source.repository_folder for source in job_packages],
        }
        recent, event = thinking_event(recent, "Starting isolated Claude Agent SDK container")
        yield event
        lease: StickySessionRuntimeLease
        try:
            lease = await asyncio.to_thread(
                self._sticky_runtime_manager.get_or_start_runtime,
                session_id=session.id,
                user_id=user_id,
                knowledge_graph_id=knowledge_graph_id,
                mode=mode.value,
                bootstrap=bootstrap,
            )
        except ContainerRuntimeError as exc:
            session.runtime_context["sticky_runtime"] = {
                "phase": "failed",
                "status": "failed",
            }
            if persist_session:
                await self._session_service.save_session(session)
            yield {
                "type": "done",
                "ok": False,
                "ready": False,
                "error": {
                    "code": "RUNTIME_START_FAILED",
                    "message": str(exc),
                },
            }
            return

        session.runtime_context["sticky_runtime"] = self._lease_context(lease, phase="starting")
        recent, event = thinking_event(
            recent,
            f"Container {lease.container_id[:8]} launched",
        )
        yield event

        runtime_base_url = lease.runtime_base_url or ""
        try:
            async for line in self._health_checker.wait_until_healthy(
                runtime_base_url=runtime_base_url,
                timeout_seconds=self._sticky_health_timeout_seconds,
            ):
                recent, event = thinking_event(recent, line)
                yield event
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
