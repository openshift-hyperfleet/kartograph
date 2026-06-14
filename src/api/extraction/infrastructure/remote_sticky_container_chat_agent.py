"""HTTP client that streams chat turns from a sticky session agent runtime container."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import GraphManagementUiMode
from extraction.infrastructure.runtime_session_auth import RUNTIME_AUTH_HEADER
from extraction.infrastructure.workload_runtime_settings import (
    get_extraction_workload_runtime_settings,
)


class RemoteStickyContainerChatAgent:
    """Delegates conversational turns to the sticky session Claude agent runtime."""

    def __init__(self, *, request_timeout_seconds: float | None = None) -> None:
        settings = get_extraction_workload_runtime_settings()
        self._request_timeout_seconds = (
            request_timeout_seconds
            if request_timeout_seconds is not None
            else settings.sticky_turn_timeout_seconds + 30.0
        )

    async def stream_turn(
        self,
        *,
        session: ExtractionAgentSession,
        user_message: str,
        ui_mode: GraphManagementUiMode,
        workload_token: str | None = None,
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

        payload: dict[str, Any] = {
            "message": user_message,
            "ui_mode": ui_mode.value,
            "agent_configuration": session.runtime_context.get("agent_configuration", {}),
            "message_history": session.message_history[-20:],
        }
        if workload_token and workload_token.strip():
            payload["workload_token"] = workload_token.strip()
        url = f"{runtime_base_url.rstrip('/')}/v1/turn"
        runtime_auth_token = sticky_runtime.get("runtime_auth_token")
        headers: dict[str, str] = {}
        if isinstance(runtime_auth_token, str) and runtime_auth_token.strip():
            headers[RUNTIME_AUTH_HEADER] = runtime_auth_token.strip()

        try:
            timeout = httpx.Timeout(10.0, read=self._request_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
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
                        await asyncio.sleep(0)
        except httpx.HTTPError as exc:
            yield {
                "type": "done",
                "ok": False,
                "error": {
                    "code": "RUNTIME_TRANSPORT_ERROR",
                    "message": str(exc),
                },
            }
