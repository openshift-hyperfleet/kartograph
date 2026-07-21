"""Relays graph-management chat turns to a user's local agent.

See specs/extraction/local-sandbox-execution.spec.md, "Chat Turn Relay
Through the Local Agent" and "Known Limitations" (buffered, not streamed).
A local Sandbox has no hosted-reachable `runtime_base_url` for the API to
call directly, so this adapter enqueues a `chat_turn` work request instead
of POSTing to the sticky container (contrast with
`RemoteStickyContainerChatAgent`). The local agent claims it, makes the same
`/v1/turn` NDJSON call against its own local Sandbox, buffers every event,
and submits them all at once on completion.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.local_runtime import LocalRuntimeWorkKind
from extraction.domain.value_objects import GraphManagementUiMode
from extraction.infrastructure.local_runtime.dispatch import (
    LocalAgentUnavailableError,
    dispatch_and_await_completion,
)

_MESSAGE_HISTORY_WINDOW = 20


class LocalStickyChatAgent:
    """Delegates conversational turns to a local agent's Sandbox, buffered."""

    def __init__(
        self,
        *,
        dispatch_timeout_seconds: float = 1000.0,
        poll_interval_seconds: float = 1.5,
        presence_timeout_seconds: float = 45.0,
    ) -> None:
        self._dispatch_timeout_seconds = dispatch_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._presence_timeout_seconds = presence_timeout_seconds

    async def stream_turn(
        self,
        *,
        session: ExtractionAgentSession,
        user_message: str,
        ui_mode: GraphManagementUiMode,
        workload_token: str | None = None,
        tenant_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        sticky = session.runtime_context.get("sticky_runtime", {})
        if sticky.get("phase") != "ready":
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "RUNTIME_UNAVAILABLE",
                    "message": "Local Sandbox runtime is unavailable.",
                },
            }
            return

        payload: dict[str, Any] = {
            "message": user_message,
            "ui_mode": ui_mode.value,
            "agent_configuration": session.runtime_context.get(
                "agent_configuration", {}
            ),
            "message_history": session.message_history[-_MESSAGE_HISTORY_WINDOW:],
        }
        if workload_token and workload_token.strip():
            payload["workload_token"] = workload_token.strip()

        try:
            completed = await dispatch_and_await_completion(
                tenant_id=tenant_id or "",
                user_id=session.user_id,
                knowledge_graph_id=session.knowledge_graph_id,
                kind=LocalRuntimeWorkKind.CHAT_TURN,
                session_id=session.id,
                payload=payload,
                dispatch_timeout_seconds=self._dispatch_timeout_seconds,
                poll_interval_seconds=self._poll_interval_seconds,
                presence_timeout_seconds=self._presence_timeout_seconds,
                unavailable_message=(
                    "No local agent is currently connected for this user. "
                    "Start your local agent and try again."
                ),
                timeout_message=(
                    "Timed out waiting for the local agent to relay this chat "
                    "turn. Ensure your local agent is running and connected."
                ),
                default_failure_message="Local agent failed to relay the chat turn.",
            )
        except LocalAgentUnavailableError as exc:
            yield {
                "type": "done",
                "ok": False,
                "error": {"code": "LOCAL_AGENT_UNAVAILABLE", "message": str(exc)},
            }
            return
        except TimeoutError as exc:
            yield {
                "type": "done",
                "ok": False,
                "error": {"code": "LOCAL_AGENT_TIMEOUT", "message": str(exc)},
            }
            return
        except RuntimeError as exc:
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "LOCAL_AGENT_CHAT_TURN_FAILED",
                    "message": str(exc),
                },
            }
            return

        events = (completed.result or {}).get("events")
        if not isinstance(events, list) or not events:
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "LOCAL_AGENT_INVALID_RESULT",
                    "message": (
                        "Local agent completed the chat turn but returned no "
                        "buffered events."
                    ),
                },
            }
            return

        for event in events:
            if isinstance(event, dict):
                yield event
