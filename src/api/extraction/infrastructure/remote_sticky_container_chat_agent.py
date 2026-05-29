"""HTTP client that streams chat turns from a sticky session agent runtime container."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import GraphManagementUiMode


class RemoteStickyContainerChatAgent:
    """Delegates conversational turns to the sticky session Claude agent runtime."""

    def __init__(self, *, request_timeout_seconds: float = 120.0) -> None:
        self._request_timeout_seconds = request_timeout_seconds

    async def stream_turn(
        self,
        *,
        session: ExtractionAgentSession,
        user_message: str,
        ui_mode: GraphManagementUiMode,
    ) -> AsyncIterator[dict[str, Any]]:
        sticky_runtime = session.runtime_context.get("sticky_runtime", {})
        runtime_base_url = sticky_runtime.get("runtime_base_url")
        if not isinstance(runtime_base_url, str) or not runtime_base_url.strip():
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "RUNTIME_UNAVAILABLE",
                    "message": "Sticky session runtime endpoint is unavailable.",
                },
            }
            return

        payload = {
            "message": user_message,
            "ui_mode": ui_mode.value,
            "agent_configuration": session.runtime_context.get("agent_configuration", {}),
            "message_history": session.message_history[-20:],
        }
        url = f"{runtime_base_url.rstrip('/')}/v1/turn"

        try:
            async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        detail = body.decode("utf-8", errors="replace")
                        yield {
                            "type": "done",
                            "ok": False,
                            "error": {
                                "code": "RUNTIME_HTTP_ERROR",
                                "message": detail or f"Agent runtime returned {response.status_code}",
                            },
                        }
                        return

                    async for line in response.aiter_lines():
                        trimmed = line.strip()
                        if not trimmed:
                            continue
                        yield json.loads(trimmed)
        except httpx.HTTPError as exc:
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "RUNTIME_TRANSPORT_ERROR",
                    "message": str(exc),
                },
            }
