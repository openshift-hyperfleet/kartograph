"""Unit tests for rolling thinking-line stream helpers."""

from __future__ import annotations

from dataclasses import dataclass

from kartograph_agent_runtime.thinking_stream import (
    initial_sdk_thinking_lines,
    push_thinking,
    replace_last_thinking,
    thinking_events_from_sdk_message,
)


@dataclass
class FakeToolUseBlock:
    name: str
    input: dict


@dataclass
class FakeThinkingBlock:
    thinking: str


@dataclass
class FakeTextBlock:
    text: str


@dataclass
class FakeAssistantMessage:
    content: list


@dataclass
class FakeTaskProgressMessage:
    task_id: str
    description: str
    last_tool_name: str | None = None
    usage: dict | None = None


@dataclass
class FakeStreamEvent:
    event: dict


def test_initial_sdk_thinking_lines_include_connected_message() -> None:
    lines = initial_sdk_thinking_lines(auth_mode="Vertex AI", ui_mode="initial-schema-design")

    assert any("Claude Agent SDK query started" in line for line in lines)
    assert any("Schema tools" in line for line in lines)


def test_agent_runtime_settings_default_max_turns() -> None:
    from kartograph_agent_runtime.settings import AgentRuntimeSettings

    settings = AgentRuntimeSettings()

    assert settings.max_turns == 500


def test_agent_runtime_settings_accepts_one_hour_turn_timeout() -> None:
    from kartograph_agent_runtime.settings import AgentRuntimeSettings

    settings = AgentRuntimeSettings(KARTOGRAPH_AGENT_TURN_TIMEOUT_SECONDS="3600")

    assert settings.turn_timeout_seconds == 3600.0


def test_push_thinking_deduplicates_and_caps_recent_lines() -> None:
    recent: list[str] = []
    for index in range(5):
        push_thinking(recent, f"line-{index}")
    assert recent == ["line-2", "line-3", "line-4"]


def test_replace_last_thinking_updates_matching_prefix_in_place() -> None:
    recent = initial_sdk_thinking_lines(auth_mode="Vertex AI", ui_mode="initial-schema-design")

    first = replace_last_thinking(
        recent,
        "Waiting for model response… (8s)",
        prefix="Waiting for model response",
    )
    second = replace_last_thinking(
        recent,
        "Waiting for model response… (16s)",
        prefix="Waiting for model response",
    )

    assert first is not None
    assert second is not None
    assert recent[-1] == "Waiting for model response… (16s)"
    assert len(recent) == 3


def test_thinking_events_from_assistant_message_tool_and_reasoning_blocks() -> None:
    recent = initial_sdk_thinking_lines(auth_mode="Vertex AI", ui_mode="initial-schema-design")
    message = FakeAssistantMessage(
        content=[
            FakeThinkingBlock(thinking="Need to inspect entity ontology first."),
            FakeToolUseBlock(name="Read", input={"file_path": "/workspace/entity_ontology.json"}),
            FakeTextBlock(text="I reviewed the ontology and found three entity types."),
        ],
    )

    events, _ = thinking_events_from_sdk_message(
        message,
        recent=recent,
        reply_parts=[],
        last_compose_at=0,
        compose_step=10,
    )

    assert events
    assert any("Reasoning" in line for line in events[-1]["recent"])
    assert any("Reading /workspace/entity_ontology.json" in line for line in events[-1]["recent"])


def test_thinking_events_from_task_progress_message() -> None:
    recent = initial_sdk_thinking_lines(auth_mode="Vertex AI", ui_mode="initial-schema-design")
    message = FakeTaskProgressMessage(
        task_id="task-1",
        description="Inspecting repository files",
        last_tool_name="Grep",
        usage={"total_tokens": 1, "tool_uses": 1, "duration_ms": 1},
    )

    events, _ = thinking_events_from_sdk_message(
        message,
        recent=recent,
        reply_parts=[],
        last_compose_at=0,
    )

    assert events
    joined = "\n".join(events[-1]["recent"])
    assert "Inspecting repository files" in joined
    assert "Running Grep" in joined


def test_stream_event_text_delta_accumulates_reply_parts() -> None:
    recent = initial_sdk_thinking_lines(auth_mode="Vertex AI", ui_mode="initial-schema-design")
    reply_parts: list[str] = []
    message = FakeStreamEvent(
        event={
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "Designed three entity types."},
        },
    )

    thinking_events_from_sdk_message(
        message,
        recent=recent,
        reply_parts=reply_parts,
        last_compose_at=0,
        compose_step=10,
    )

    assert reply_parts == ["Designed three entity types."]


def test_assistant_message_text_accumulates_reply_parts() -> None:
    recent = initial_sdk_thinking_lines(auth_mode="Vertex AI", ui_mode="initial-schema-design")
    reply_parts: list[str] = []
    message = FakeAssistantMessage(
        content=[FakeTextBlock(text="Here is the proposed schema.")],
    )

    thinking_events_from_sdk_message(
        message,
        recent=recent,
        reply_parts=reply_parts,
        last_compose_at=0,
        compose_step=120,
    )

    assert reply_parts == ["Here is the proposed schema."]
