"""Rolling thinking-line panel updates for NDJSON chat streams."""

from __future__ import annotations

from typing import Any

# Rolling window surfaced to the Graph Management Assistant UI (last N thoughts).
_MAX_THINKING_LINES = 3


def normalize_activity_line(text: str) -> str:
    line = " ".join(text.split())
    if len(line) > 120:
        return line[:117] + "…"
    return line


def push_thinking(recent: list[str], line: str) -> dict[str, Any] | None:
    normalized = normalize_activity_line(line)
    if not normalized:
        return None
    if recent and recent[-1] == normalized:
        return None
    recent.append(normalized)
    if len(recent) > _MAX_THINKING_LINES:
        recent[:] = recent[-_MAX_THINKING_LINES:]
    return {"type": "thinking", "recent": list(recent)}


def replace_last_thinking(
    recent: list[str],
    line: str,
    *,
    prefix: str | None = None,
) -> dict[str, Any] | None:
    """Replace the last matching (or final) thinking line — used for heartbeats."""
    normalized = normalize_activity_line(line)
    if not normalized:
        return None
    if prefix:
        for index in range(len(recent) - 1, -1, -1):
            if str(recent[index]).startswith(prefix):
                if recent[index] == normalized:
                    return None
                recent[index] = normalized
                return {"type": "thinking", "recent": list(recent)}
    if recent:
        if recent[-1] == normalized:
            return None
        recent[-1] = normalized
    else:
        recent.append(normalized)
    return {"type": "thinking", "recent": list(recent)}


def update_composing_line(recent: list[str], preview_tail: str) -> dict[str, Any] | None:
    preview_tail = normalize_activity_line(preview_tail.replace("\n", " "))
    line = normalize_activity_line(
        f"Composing reply · {preview_tail}" if preview_tail else "Composing reply…",
    )
    prefix = "Composing reply"
    if recent and str(recent[-1]).startswith(prefix):
        recent[-1] = line
        return {"type": "thinking", "recent": list(recent)}
    return push_thinking(recent, line)


def _tool_use_line(name: str, tool_input: dict[str, Any]) -> str:
    if name == "Read":
        path = tool_input.get("file_path") or tool_input.get("path") or ""
        return f"Reading {path}" if path else "Reading file…"
    if name in {"Write", "Edit"}:
        path = tool_input.get("file_path") or tool_input.get("path") or ""
        verb = "Writing" if name == "Write" else "Editing"
        return f"{verb} {path}" if path else f"{verb} file…"
    if name == "Grep":
        pattern = tool_input.get("pattern") or ""
        return f"Searching for {pattern}" if pattern else "Searching repository…"
    if name == "Glob":
        pattern = tool_input.get("pattern") or ""
        return f"Listing files {pattern}" if pattern else "Listing files…"
    if name == "Bash":
        command = tool_input.get("command") or ""
        return f"Running {command}" if command else "Running shell command…"
    if name.startswith("kartograph_"):
        readable = name.removeprefix("kartograph_").replace("_", " ")
        return f"Schema tool · {readable}"
    return f"Running {name}…"


def _stream_event_line(event: dict[str, Any]) -> str | None:
    event_type = event.get("type")
    if event_type == "content_block_start":
        block = event.get("content_block") or {}
        block_type = block.get("type")
        if block_type == "tool_use":
            name = block.get("name") or "tool"
            return f"Running {name}…"
        if block_type == "thinking":
            return "Reasoning…"
        if block_type == "text":
            return "Composing reply…"
    if event_type == "content_block_delta":
        delta = event.get("delta") or {}
        if delta.get("type") == "thinking_delta":
            thinking = str(delta.get("thinking") or "").strip()
            if thinking:
                return f"Reasoning · {normalize_activity_line(thinking)}"
    return None


def _thinking_events_from_stream_event(
    event: dict[str, Any],
    *,
    recent: list[str],
    reply_parts: list[str],
    last_compose_at: int,
    compose_step: int,
) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    if event.get("type") == "content_block_delta":
        delta = event.get("delta") or {}
        if delta.get("type") == "text_delta":
            text = str(delta.get("text") or "")
            if text:
                reply_parts.append(text)
                blob = "".join(reply_parts)
                if len(blob.strip()) and len(blob) - last_compose_at >= compose_step:
                    tail = blob[-88:].replace("\n", " ").strip()
                    compose_event = update_composing_line(recent, tail)
                    if compose_event:
                        events.append(compose_event)
                    last_compose_at = len(blob)
            return events, last_compose_at

    line = _stream_event_line(event)
    if line:
        compose_event = push_thinking(recent, line)
        if compose_event:
            events.append(compose_event)
    return events, last_compose_at


def _append_task_progress_events(
    events: list[dict[str, Any]],
    recent: list[str],
    *,
    description: str,
    last_tool_name: str | None,
    started: bool,
) -> None:
    progress_description = description.strip()
    last_tool = str(last_tool_name or "").strip()
    if progress_description:
        prefix = "Task started · " if started else ""
        event = push_thinking(recent, f"{prefix}{progress_description}".strip())
        if event:
            events.append(event)
    if last_tool:
        event = push_thinking(recent, f"Running {last_tool}…")
        if event:
            events.append(event)


def _thinking_events_from_assistant_content(
    content: list[Any],
    *,
    recent: list[str],
    reply_parts: list[str],
    last_compose_at: int,
    compose_step: int,
) -> tuple[list[dict[str, Any]], int]:
    from claude_agent_sdk.types import TextBlock, ThinkingBlock, ToolUseBlock

    events: list[dict[str, Any]] = []
    for block in content:
        if isinstance(block, ThinkingBlock):
            thinking = normalize_activity_line(block.thinking or "")
            if thinking:
                event = push_thinking(recent, f"Reasoning · {thinking}")
                if event:
                    events.append(event)
        elif isinstance(block, ToolUseBlock):
            tool_input = block.input if isinstance(block.input, dict) else {}
            event = push_thinking(recent, _tool_use_line(block.name, tool_input))
            if event:
                events.append(event)
        elif isinstance(block, TextBlock):
            text = str(block.text or "")
            if text.strip():
                reply_parts.append(text)
                blob = "".join(reply_parts)
                plain = text.replace("\n", "").strip()
                if plain and len(blob) - last_compose_at >= compose_step:
                    tail = blob[-88:].replace("\n", " ").strip()
                    event = update_composing_line(recent, tail)
                    if event:
                        events.append(event)
                    last_compose_at = len(blob)
        else:
            block_type = type(block).__name__
            if block_type == "ThinkingBlock" or hasattr(block, "thinking"):
                thinking = normalize_activity_line(getattr(block, "thinking", "") or "")
                if thinking:
                    event = push_thinking(recent, f"Reasoning · {thinking}")
                    if event:
                        events.append(event)
            elif block_type == "ToolUseBlock" or hasattr(block, "name"):
                name = str(getattr(block, "name", "") or "tool")
                tool_input = getattr(block, "input", None) or {}
                if not isinstance(tool_input, dict):
                    tool_input = {}
                event = push_thinking(recent, _tool_use_line(name, tool_input))
                if event:
                    events.append(event)
            elif block_type == "TextBlock" or hasattr(block, "text"):
                text = str(getattr(block, "text", "") or "")
                if text.strip():
                    reply_parts.append(text)
                    blob = "".join(reply_parts)
                    plain = text.replace("\n", "").strip()
                    if plain and len(blob) - last_compose_at >= compose_step:
                        tail = blob[-88:].replace("\n", " ").strip()
                        event = update_composing_line(recent, tail)
                        if event:
                            events.append(event)
                        last_compose_at = len(blob)
    return events, last_compose_at


def thinking_events_from_sdk_message(
    sdk_message: Any,
    *,
    recent: list[str],
    reply_parts: list[str],
    last_compose_at: int,
    compose_step: int = 120,
) -> tuple[list[dict[str, Any]], int]:
    """Return thinking NDJSON events and updated compose offset for one SDK message."""
    from claude_agent_sdk.types import (
        AssistantMessage,
        StreamEvent,
        TaskNotificationMessage,
        TaskProgressMessage,
        TaskStartedMessage,
    )

    events: list[dict[str, Any]] = []

    if isinstance(sdk_message, AssistantMessage):
        if isinstance(sdk_message.content, list):
            return _thinking_events_from_assistant_content(
                sdk_message.content,
                recent=recent,
                reply_parts=reply_parts,
                last_compose_at=last_compose_at,
                compose_step=compose_step,
            )
        return events, last_compose_at

    if isinstance(sdk_message, TaskStartedMessage):
        _append_task_progress_events(
            events,
            recent,
            description=str(sdk_message.description or ""),
            last_tool_name=None,
            started=True,
        )
        return events, last_compose_at

    if isinstance(sdk_message, TaskProgressMessage):
        _append_task_progress_events(
            events,
            recent,
            description=str(sdk_message.description or ""),
            last_tool_name=sdk_message.last_tool_name,
            started=False,
        )
        return events, last_compose_at

    if isinstance(sdk_message, TaskNotificationMessage):
        summary = str(sdk_message.summary or "").strip()
        if summary:
            event = push_thinking(recent, summary)
            if event:
                events.append(event)
        return events, last_compose_at

    if isinstance(sdk_message, StreamEvent):
        return _thinking_events_from_stream_event(
            sdk_message.event,
            recent=recent,
            reply_parts=reply_parts,
            last_compose_at=last_compose_at,
            compose_step=compose_step,
        )

    content = getattr(sdk_message, "content", None)
    if isinstance(content, list):
        return _thinking_events_from_assistant_content(
            content,
            recent=recent,
            reply_parts=reply_parts,
            last_compose_at=last_compose_at,
            compose_step=compose_step,
        )

    task_id = getattr(sdk_message, "task_id", None)
    description = str(getattr(sdk_message, "description", "") or "").strip()
    if task_id and description:
        _append_task_progress_events(
            events,
            recent,
            description=description,
            last_tool_name=getattr(sdk_message, "last_tool_name", None),
            started=getattr(sdk_message, "usage", None) is None
            and not getattr(sdk_message, "last_tool_name", None),
        )
        return events, last_compose_at

    payload = getattr(sdk_message, "event", None)
    if isinstance(payload, dict):
        return _thinking_events_from_stream_event(
            payload,
            recent=recent,
            reply_parts=reply_parts,
            last_compose_at=last_compose_at,
            compose_step=compose_step,
        )

    return events, last_compose_at


def initial_sdk_thinking_lines(*, auth_mode: str, ui_mode: str) -> list[str]:
    return [
        f"Claude Agent SDK query started ({auth_mode})…",
        f"Mode overlay: {ui_mode}",
        "Schema tools: ontology read/save, JSONL mutations, graph search",
    ]
