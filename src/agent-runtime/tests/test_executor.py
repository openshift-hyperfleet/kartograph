"""Unit tests for agent runtime executor fallback mode."""

from __future__ import annotations

import pytest

from kartograph_agent_runtime.executor import stream_turn_events
from kartograph_agent_runtime.settings import AgentRuntimeSettings


@pytest.mark.asyncio
async def test_stream_turn_events_without_api_key_returns_done_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
    monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = AgentRuntimeSettings(
        KARTOGRAPH_WORKLOAD_TOKEN="token",
        KARTOGRAPH_API_BASE_URL="http://api:8000",
        ANTHROPIC_API_KEY="",
    )

    events = [
        event
        async for event in stream_turn_events(
            settings=settings,
            message="Design entity types",
            ui_mode="initial-schema-design",
            agent_configuration={"skills": {"schema_modeling": "guide"}},
            message_history=[],
        )
    ]

    assert events[0]["type"] == "thinking"
    assert events[-1]["type"] == "done"
    assert events[-1]["ok"] is True
    assert "Graph Management Assistant" in events[-1]["reply"]
