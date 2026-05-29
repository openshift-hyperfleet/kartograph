"""HTTP server for sticky session agent runtime."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kartograph_agent_runtime.executor import stream_turn_events
from kartograph_agent_runtime.settings import AgentRuntimeSettings

logger = logging.getLogger(__name__)

app = FastAPI(title="Kartograph Agent Runtime", version="0.1.0")
settings = AgentRuntimeSettings()


class TurnRequest(BaseModel):
    message: str = Field(min_length=1)
    ui_mode: str = Field(default="initial-schema-design")
    agent_configuration: dict[str, Any] = Field(default_factory=dict)
    message_history: list[dict[str, Any]] = Field(default_factory=list)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "session_id": settings.session_id}


@app.post("/v1/turn")
async def stream_turn(request: TurnRequest) -> StreamingResponse:
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
            ):
                if event.get("type") == "done":
                    logger.info(
                        "agent_runtime_turn_finished session_id=%s ok=%s",
                        settings.session_id,
                        event.get("ok"),
                    )
                yield json.dumps(event) + "\n"
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

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
