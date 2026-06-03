"""Unit tests for agent runtime executor fallback mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kartograph_agent_runtime.executor import (
    _build_system_prompt,
    _build_workspace_prompt_appendix,
    _extract_sdk_reply,
    finalize_sdk_turn_reply,
    stream_turn_events,
)
from kartograph_agent_runtime.settings import AgentRuntimeSettings


def test_build_workspace_prompt_appendix_prefers_sources_index(tmp_path: Path) -> None:
    package_id = "pkg-1"
    package_root = tmp_path / "repository-files" / package_id / "pkg" / "api"
    package_root.mkdir(parents=True)
    (package_root / "adapter_status_types_test.go").write_text("package api\n", encoding="utf-8")
    (tmp_path / "sources-index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "knowledge_graph_id": "kg-1",
                "sources": [
                    {
                        "job_package_id": package_id,
                        "data_source_id": "ds-hyperfleet-api",
                        "entry_count": 142,
                        "repository_root": f"repository-files/{package_id}",
                        "sample_paths": ["pkg/api/adapter_status_types_test.go"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    appendix = _build_workspace_prompt_appendix(
        AgentRuntimeSettings(KARTOGRAPH_WORKSPACE_DIR=str(tmp_path))
    )

    assert "ds-hyperfleet-api" in appendix
    assert "142 file(s)" in appendix
    assert "pkg/api/adapter_status_types_test.go" in appendix


def test_build_workspace_prompt_appendix_lists_materialized_repository_files(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "repository-files" / "pkg-1" / "pkg" / "api"
    package_root.mkdir(parents=True)
    (package_root / "adapter_status_types_test.go").write_text("package api\n", encoding="utf-8")

    appendix = _build_workspace_prompt_appendix(
        AgentRuntimeSettings(KARTOGRAPH_WORKSPACE_DIR=str(tmp_path))
    )

    assert "repository-files/<job_package_id>/" in appendix
    assert "pkg/api/adapter_status_types_test.go" in appendix


def test_build_system_prompt_includes_workspace_appendix() -> None:
    prompt = _build_system_prompt(
        {"system_prompt": "Base prompt"},
        workspace_appendix="## Session workspace\nFiles here",
    )

    assert "Base prompt" in prompt
    assert "Files here" in prompt


def test_extract_sdk_reply_joins_multiple_text_blocks() -> None:
    from dataclasses import dataclass

    @dataclass
    class Block:
        text: str

    @dataclass
    class Message:
        content: list

    message = Message(content=[Block(text="Part one. "), Block(text="Part two.")])

    assert _extract_sdk_reply(message) == "Part one. Part two."


def test_finalize_sdk_turn_reply_prefers_streamed_text() -> None:
    reply = finalize_sdk_turn_reply(
        reply=None,
        reply_parts=["Designed ", "entity types."],
        last_result=None,
        notification_summaries=[],
    )

    assert reply == "Designed entity types."


def test_finalize_sdk_turn_reply_uses_tool_only_completion_summary() -> None:
    from dataclasses import dataclass

    @dataclass
    class Result:
        num_turns: int
        result: str | None = None
        is_error: bool = False

    reply = finalize_sdk_turn_reply(
        reply=None,
        reply_parts=[],
        last_result=Result(num_turns=4),
        notification_summaries=[],
    )

    assert "4 turn(s)" in reply
    assert "without a final written reply" in reply


def test_finalize_sdk_turn_reply_returns_none_when_nothing_available() -> None:
    reply = finalize_sdk_turn_reply(
        reply=None,
        reply_parts=[],
        last_result=None,
        notification_summaries=[],
    )

    assert reply is None


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
