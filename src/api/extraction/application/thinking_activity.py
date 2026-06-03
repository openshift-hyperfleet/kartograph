"""Rolling thinking-line helpers for NDJSON chat streams."""

from __future__ import annotations

from typing import Any

MAX_THINKING_LINES = 3


def append_thinking_line(recent: list[str], line: str) -> list[str]:
    normalized = " ".join(line.split())
    if not normalized:
        return list(recent)
    if recent and recent[-1] == normalized:
        return list(recent)
    updated = [*recent, normalized]
    if len(updated) > MAX_THINKING_LINES:
        updated = updated[-MAX_THINKING_LINES:]
    return updated


def thinking_event(recent: list[str], line: str) -> tuple[list[str], dict[str, Any]]:
    updated = append_thinking_line(recent, line)
    return updated, {"type": "thinking", "recent": updated}
