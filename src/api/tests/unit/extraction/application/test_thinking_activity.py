"""Unit tests for rolling thinking activity helpers."""

from __future__ import annotations

from extraction.application.thinking_activity import (
    MAX_THINKING_LINES,
    append_thinking_line,
    thinking_event,
)


def test_append_thinking_line_caps_at_three() -> None:
    recent: list[str] = []
    for line in ("one", "two", "three", "four"):
        recent = append_thinking_line(recent, line)

    assert recent == ["two", "three", "four"]
    assert MAX_THINKING_LINES == 3


def test_thinking_event_returns_full_recent_window() -> None:
    recent, event = thinking_event([], "Starting container")

    assert event == {"type": "thinking", "recent": ["Starting container"]}
    assert recent == ["Starting container"]

    recent, event = thinking_event(recent, "Waiting for health check")
    assert event["recent"] == ["Starting container", "Waiting for health check"]
