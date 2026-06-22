"""Orchestrates graph-management chat turns with sticky runtime and streaming events."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.application.graph_management_session_journal import (
    append_turn_usage_to_session,
)
from extraction.ports.sticky_session_runtime import IStickySessionRuntimeService
from extraction.domain.value_objects import (
    ExtractionSessionMode,
    GraphManagementUiMode,
    SessionJobPackagePhase,
)
from extraction.ports.runtime import IWorkloadCredentialIssuer
from extraction.ports.chat_agent import IExtractionChatAgent


class ExtractionChatTurnService:
    """Coordinates sticky runtime, JobPackage gating, and agent execution."""

    def __init__(
        self,
        *,
        session_service: ExtractionAgentSessionService,
        runtime_service: IStickySessionRuntimeService,
        chat_agent: IExtractionChatAgent,
        credential_issuer: IWorkloadCredentialIssuer | None = None,
    ) -> None:
        self._session_service = session_service
        self._runtime_service = runtime_service
        self._chat_agent = chat_agent
        self._credential_issuer = credential_issuer

    async def stream_runtime_warmup(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in self._runtime_service.stream_runtime_warmup(
            tenant_id=tenant_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            ui_mode=ui_mode,
        ):
            yield event

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

        session = await self._session_service.get_active_session(
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            ui_mode=ui_mode,
        )
        if session is None:
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "SESSION_NOT_STARTED",
                    "message": "Start a Graph Management Assistant session before chatting.",
                },
            }
            return

        async for event in self._runtime_service.ensure_runtime_for_chat(
            tenant_id=tenant_id,
            user_id=user_id,
            knowledge_graph_id=knowledge_graph_id,
            mode=mode,
            ui_mode=ui_mode,
            session=session,
        ):
            yield event

        job_package_phase = session.runtime_context.get("job_package", {}).get("phase")
        if job_package_phase == SessionJobPackagePhase.AWAITING_PREPARE.value:
            wait_message = (
                session.runtime_context.get(
                    "activity_lines", ["Waiting for JobPackage ingestion context."]
                )[0]
                if session.runtime_context.get("activity_lines")
                else "Waiting for JobPackage ingestion context."
            )
            session.message_history.append({"role": "user", "content": trimmed})
            assistant_reply = (
                f"**Waiting for ingestion context**\n\n{wait_message}\n\n"
                "I'll respond with full repository-aware guidance once JobPackage "
                "material is prepared for this knowledge graph."
            )
            session.message_history.append(
                {"role": "assistant", "content": assistant_reply}
            )
            session.updated_at = datetime.now(UTC)
            await self._session_service.save_session(session)
            yield {"type": "done", "ok": True, "reply": assistant_reply, "wait": True}
            return

        sticky = session.runtime_context.get("sticky_runtime", {})
        if sticky.get("phase") != "ready":
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "RUNTIME_NOT_READY",
                    "message": "Graph Management Assistant runtime is not ready yet.",
                },
            }
            return

        yield {
            "type": "thinking",
            "recent": [
                "Contacting Graph Management Assistant…",
                f"Sticky container {str(sticky.get('container_id', ''))[:8]} active",
            ],
        }

        workload_token: str | None = None
        if self._credential_issuer is not None:
            workload_token = self._credential_issuer.issue_for_sticky_session(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                session_id=session.id,
            ).token

        assistant_reply: str | None = None
        stream_failed = False
        async for event in self._chat_agent.stream_turn(
            session=session,
            user_message=trimmed,
            ui_mode=ui_mode,
            workload_token=workload_token,
        ):
            if event.get("type") == "thinking":
                recent = event.get("recent")
                if isinstance(recent, list):
                    session.runtime_context["activity_lines"] = [
                        str(line) for line in recent if str(line).strip()
                    ]
            if event.get("type") == "done":
                usage = event.get("usage")
                if isinstance(usage, dict) and usage:
                    append_turn_usage_to_session(session, usage=usage)
                if event.get("ok") is True and event.get("reply"):
                    assistant_reply = str(event["reply"])
                elif event.get("ok") is not True:
                    stream_failed = True
            yield event

        if assistant_reply:
            session.message_history.append({"role": "user", "content": trimmed})
            session.message_history.append(
                {"role": "assistant", "content": assistant_reply}
            )
            session.updated_at = datetime.now(UTC)
            session.runtime_context.pop("activity_lines", None)
            await self._session_service.save_session(session)
        elif stream_failed:
            session.message_history.append({"role": "user", "content": trimmed})
            session.updated_at = datetime.now(UTC)
            await self._session_service.save_session(session)
        elif session.runtime_context.get("mutation_journal"):
            session.updated_at = datetime.now(UTC)
            await self._session_service.save_session(session)
        else:
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "AGENT_STREAM_INCOMPLETE",
                    "message": (
                        "Graph Management Assistant ended the turn without a final response. "
                        "Check sticky container logs for Vertex or SDK errors."
                    ),
                },
            }
