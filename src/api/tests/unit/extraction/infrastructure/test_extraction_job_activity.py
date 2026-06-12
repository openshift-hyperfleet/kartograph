"""Unit tests for extraction job activity logs."""

from __future__ import annotations

import json
from pathlib import Path

from extraction.infrastructure.extraction_job_activity import (
    append_activity_line,
    append_activity_message,
    format_claude_code_stream_line,
    parse_activity_messages,
    read_assistant_preview,
    read_activity_log,
)


def test_format_claude_code_stream_line_parses_assistant_thoughts() -> None:
    payload = json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Inspecting adapter configuration files."},
                    {"type": "tool_use", "name": "Read", "input": {"path": "job-context.json"}},
                ]
            },
        }
    )
    messages = format_claude_code_stream_line(payload)
    assert messages == [
        ("thought", "Inspecting adapter configuration files."),
        ("tool", "Using tool: Read"),
    ]


def test_format_claude_code_stream_line_parses_result_error() -> None:
    payload = json.dumps(
        {
            "type": "result",
            "is_error": True,
            "result": "API Error: Could not load the default credentials.",
        }
    )
    assert format_claude_code_stream_line(payload) == [
        ("error", "API Error: Could not load the default credentials.")
    ]


def test_parse_activity_messages_expands_legacy_json_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "agent_activity.log"
    append_activity_line(log_path, "📡 Processing job adapter_batch_0001_abcd")
    append_activity_message(log_path, kind="system", text="Agent initialized (model: claude-opus-4-6)")
    append_activity_message(log_path, kind="thought", text="Scanning repository-files for adapter config")
    append_activity_message(log_path, kind="error", text="API Error: Could not load the default credentials.")

    messages = parse_activity_messages(read_activity_log(tmp_path))

    assert len(messages) >= 4
    assert messages[0]["kind"] == "info"
    assert any(message["kind"] == "thought" for message in messages)
    assert messages[-1]["text"].startswith("API Error")


def test_read_assistant_preview_returns_latest_thought_for_job(tmp_path: Path) -> None:
    log_path = tmp_path / "agent_activity.log"
    append_activity_line(log_path, "📡 Processing job adapter_batch_0001_abcd")
    append_activity_message(log_path, kind="thought", text="Scanning repository-files for adapter config")
    append_activity_message(log_path, kind="tool", text="Using tool: kartograph_apply_graph_mutations")
    append_activity_message(log_path, kind="thought", text="Linked adapter to three Resource entities")

    preview = read_assistant_preview(tmp_path, job_id="adapter_batch_0001_abcd")

    assert preview == "Linked adapter to three Resource entities"


def test_read_activity_log_returns_empty_when_missing(tmp_path: Path) -> None:
    assert read_activity_log(tmp_path) == ""
