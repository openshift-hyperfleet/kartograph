"""Rolling thinking-line panel updates for NDJSON chat streams."""

from __future__ import annotations

from typing import Any

_MAX_THINKING_LINES = 8


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
    if event_type == "content_block_delta":
        delta = event.get("delta") or {}
        if delta.get("type") == "thinking_delta":
            thinking = str(delta.get("thinking") or "").strip()
            if thinking:
                return f"Reasoning · {normalize_activity_line(thinking)}"
        if delta.get("type") == "text_delta":
            text = str(delta.get("text") or "").strip()
            if text:
                return None  # handled via composing line from accumulated text
    return None


def thinking_events_from_sdk_message(
    sdk_message: Any,
    *,
    recent: list[str],
    reply_parts: list[str],
    last_compose_at: int,
    compose_step: int = 120,
) -> tuple[list[dict[str, Any]], int]:
    """Return thinking NDJSON events and updated compose offset for one SDK message."""
    events: list[dict[str, Any]] = []

    content = getattr(sdk_message, "content", None)
    if isinstance(content, list):
        for block in content:
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

    task_id = getattr(sdk_message, "task_id", None)
    description = str(getattr(sdk_message, "description", "") or "").strip()
    if task_id and description:
        last_tool = str(getattr(sdk_message, "last_tool_name", "") or "").strip()
        usage = getattr(sdk_message, "usage", None)
        prefix = "Task started ·" if usage is None and not last_tool else ""
        line = f"{prefix}{description}".strip()
        event = push_thinking(recent, line)
        if event:
            events.append(event)
        if last_tool:
            event = push_thinking(recent, f"Running {last_tool}…")
            if event:
                events.append(event)
        return events, last_compose_at

    payload = getattr(sdk_message, "event", None)
    if isinstance(payload, dict):
        line = _stream_event_line(payload)
        if line:
            event = push_thinking(recent, line)
            if event:
                events.append(event)
        return events, last_compose_at

    subtype = str(getattr(sdk_message, "subtype", "") or "").strip()
    data = getattr(sdk_message, "data", None) or {}
    if subtype == "task_progress" and isinstance(data, dict):
        progress_description = str(data.get("description") or "").strip()
        last_tool = str(data.get("last_tool_name") or "").strip()
        if progress_description:
            event = push_thinking(recent, progress_description)
            if event:
                events.append(event)
        if last_tool:
            event = push_thinking(recent, f"Running {last_tool}…")
            if event:
                events.append(event)

    return events, last_compose_at


def initial_sdk_thinking_lines(*, auth_mode: str, ui_mode: str) -> list[str]:
    return [
        f"Claude Agent SDK query started ({auth_mode})…",
        f"Mode overlay: {ui_mode}",
        "Tools: graph read enclave, mutation emitter",
        "Connected — working on your message…",
    ]
