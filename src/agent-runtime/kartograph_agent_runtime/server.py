"""HTTP server for sticky session agent runtime."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from kartograph_agent_runtime.executor import stream_turn_events
from kartograph_agent_runtime.settings import AgentRuntimeSettings
from kartograph_agent_runtime.runtime_auth import runtime_auth_matches, RUNTIME_AUTH_HEADER

logger = logging.getLogger(__name__)

app = FastAPI(title="Kartograph Agent Runtime", version="0.1.0")
settings = AgentRuntimeSettings()


class TurnRequest(BaseModel):
    message: str = Field(min_length=1)
    ui_mode: str = Field(default="initial-schema-design")
    agent_configuration: dict[str, Any] = Field(default_factory=dict)
    message_history: list[dict[str, Any]] = Field(default_factory=list)
    workload_token: str | None = Field(
        default=None,
        description="Fresh scoped JWT for Kartograph schema/mutation tools (preferred over container env).",
    )


def _workspace_ready() -> bool:
    marker = Path(settings.workspace_dir) / "knowledge-graph-id"
    return marker.is_file()


@app.get("/health")
async def health():
    if not _workspace_ready():
        return JSONResponse(
            status_code=503,
            content={
                "status": "workspace_unavailable",
                "session_id": settings.session_id,
            },
        )
    return {"status": "ok", "session_id": settings.session_id}


def _require_runtime_auth(runtime_auth: str | None) -> None:
    expected = settings.runtime_auth_token.strip()
    if not expected:
        return
    if not runtime_auth_matches(expected=expected, provided=runtime_auth or ""):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "RUNTIME_AUTH_REQUIRED",
                "message": "Missing or invalid runtime auth token.",
            },
        )


@app.post("/v1/turn")
async def stream_turn(
    request: TurnRequest,
    x_kartograph_runtime_auth: str | None = Header(default=None, alias=RUNTIME_AUTH_HEADER),
) -> StreamingResponse:
    _require_runtime_auth(x_kartograph_runtime_auth)
    logger.info(
        "agent_runtime_turn_started session_id=%s ui_mode=%s message_len=%s",
        settings.session_id,
        request.ui_mode,
        len(request.message),
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in stream_turn_events(
                settings=settings,
                message=request.message,
                ui_mode=request.ui_mode,
                agent_configuration=request.agent_configuration,
                message_history=request.message_history,
                turn_timeout_seconds=settings.turn_timeout_seconds,
                workload_token=request.workload_token,
            ):
                if event.get("type") == "done":
                    logger.info(
                        "agent_runtime_turn_finished session_id=%s ok=%s",
                        settings.session_id,
                        event.get("ok"),
                    )
                yield json.dumps(event) + "\n"
                await asyncio.sleep(0)
        except Exception:
            logger.exception(
                "agent_runtime_turn_failed session_id=%s",
                settings.session_id,
            )
            yield (
                json.dumps(
                    {
                        "type": "done",
                        "ok": False,
                        "error": {
                            "code": "AGENT_RUNTIME_INTERNAL_ERROR",
                            "message": "Agent runtime failed while processing the turn.",
                        },
                    }
                )
                + "\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
