"""Read and write per-job agent activity logs for live extraction UI."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionJobStatus
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)

AGENT_ACTIVITY_LOG = "agent_activity.log"
_PREVIEW_MAX_LEN = 220
_ACTIVITY_KIND_EMOJI = {
    "info": "📡",
    "system": "⚙️",
    "thought": "💭",
    "tool": "🔧",
    "error": "❌",
    "success": "✅",
}


def job_workdir(
    *,
    knowledge_graph_id: str,
    job_id: str,
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> Path:
    runtime = settings or get_extraction_workload_runtime_settings()
    return Path(runtime.extraction_job_work_dir) / knowledge_graph_id / job_id


def activity_log_path(workdir: Path) -> Path:
    return workdir / AGENT_ACTIVITY_LOG


def append_activity_line(log_path: Path, message: str) -> None:
    ts = datetime.now(UTC).isoformat()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{ts} {message}\n")


def format_activity_log_line(*, kind: str, text: str) -> str:
    emoji = _ACTIVITY_KIND_EMOJI.get(kind, "•")
    return f"{emoji} {text.strip()}"


def append_activity_message(log_path: Path, *, kind: str, text: str) -> None:
    if not text.strip():
        return
    append_activity_line(log_path, format_activity_log_line(kind=kind, text=text))


def format_claude_code_stream_line(raw_line: str) -> list[tuple[str, str]]:
    """Parse one claude-code JSONL stdout line into human-readable activity messages."""
    stripped = raw_line.strip()
    if not stripped:
        return []
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        if stripped.startswith("{"):
            return []
        return [("info", stripped)]

    event_type = str(event.get("type") or "")
    if event_type == "assistant":
        message = event.get("message") or {}
        blocks = message.get("content") or []
        rendered: list[tuple[str, str]] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "")
            if block_type == "text":
                text = str(block.get("text") or "").strip()
                if text:
                    rendered.append(("thought", text))
            elif block_type == "tool_use":
                tool_name = str(block.get("name") or "tool")
                rendered.append(("tool", f"Using tool: {tool_name}"))
            elif block_type == "thinking":
                text = str(block.get("thinking") or block.get("text") or "").strip()
                if text:
                    rendered.append(("thought", text))
        return rendered

    if event_type == "system":
        subtype = str(event.get("subtype") or "")
        if subtype == "init":
            model = str(event.get("model") or "unknown")
            return [("system", f"Agent initialized (model: {model})")]
        if subtype == "status":
            status = str(event.get("status") or "working")
            return [("system", f"Status: {status}")]
        return []

    if event_type == "result":
        if event.get("is_error"):
            error_text = str(event.get("result") or event.get("error") or "Extraction failed")
            return [("error", error_text)]
        result_text = str(event.get("result") or "").strip()
        if result_text:
            return [("success", result_text[:500])]
        return [("success", "Job completed")]

    return []


def _split_log_line(line: str) -> tuple[str, str, str]:
    """Return (timestamp, kind, body) parsed from one stored log line."""
    timestamp = ""
    body = line.strip()
    if body and body[0].isdigit():
        parts = body.split(" ", 1)
        if len(parts) == 2 and "T" in parts[0]:
            timestamp, body = parts[0], parts[1]

    for emoji, kind in (
        ("📡", "info"),
        ("⚙️", "system"),
        ("💭", "thought"),
        ("🔧", "tool"),
        ("❌", "error"),
        ("✅", "success"),
    ):
        prefix = f"{emoji} "
        if body.startswith(prefix):
            return timestamp, kind, body[len(prefix) :].strip()

    return timestamp, "info", body


def parse_activity_messages(raw_log: str) -> list[dict[str, str]]:
    """Expand stored activity log lines into UI-friendly message rows."""
    messages: list[dict[str, str]] = []
    for line in raw_log.splitlines():
        if not line.strip():
            continue
        timestamp, kind, body = _split_log_line(line)
        if body.startswith("{") and body.endswith("}"):
            for parsed_kind, parsed_text in format_claude_code_stream_line(body):
                messages.append(
                    {
                        "timestamp": timestamp,
                        "kind": parsed_kind,
                        "text": parsed_text,
                    }
                )
            continue
        messages.append({"timestamp": timestamp, "kind": kind, "text": body})
    return messages


def read_activity_log(workdir: Path) -> str:
    path = activity_log_path(workdir)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def read_assistant_preview(workdir: Path, *, job_id: str) -> str | None:
    """Return the latest thought/tool/error line for one job from its activity log."""
    content = read_activity_log(workdir)
    if not content.strip():
        return None

    lines = [line for line in content.splitlines() if line.strip()]
    start_idx = -1
    marker = f"Processing job {job_id}"
    for index in range(len(lines) - 1, -1, -1):
        if marker in lines[index]:
            start_idx = index
            break

    section_start = start_idx if start_idx >= 0 else 0
    section_end = len(lines)
    for index in range(section_start + 1, len(lines)):
        if "Processing job " in lines[index] and marker not in lines[index]:
            section_end = index
            break

    for index in range(section_end - 1, section_start - 1, -1):
        messages = parse_activity_messages(lines[index])
        if messages:
            for message in reversed(messages):
                if message["kind"] in {"thought", "tool", "error", "success", "system"}:
                    return message["text"][:_PREVIEW_MAX_LEN]
        line = lines[index]
        for prefix in ("💭 ", "🔧 ", "❌ ", "⚙️ ", "✅ ", "📡 "):
            marker_idx = line.find(prefix)
            if marker_idx >= 0:
                return line[marker_idx + len(prefix) :].strip()[:_PREVIEW_MAX_LEN]
    return None


def serialize_recent_job(
    job: ExtractionJobRecord,
    *,
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> dict[str, Any]:
    """Shape one job row for database-status recentJobs and live activity UI."""
    runtime = settings or get_extraction_workload_runtime_settings()
    workdir = job_workdir(
        knowledge_graph_id=job.knowledge_graph_id,
        job_id=job.job_id,
        settings=runtime,
    )
    preview = read_assistant_preview(workdir, job_id=job.job_id)
    if not preview and job.status == ExtractionJobStatus.FAILED and job.error_message:
        preview = job.error_message[:_PREVIEW_MAX_LEN]
    if not preview and job.description:
        preview = job.description[:_PREVIEW_MAX_LEN]

    return {
        "jobId": job.job_id,
        "jobSet": job.job_set_name,
        "status": job.status.value,
        "workerId": job.worker_id,
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "completedAt": job.completed_at.isoformat() if job.completed_at else None,
        "inputTokens": job.input_tokens,
        "outputTokens": job.output_tokens,
        "cacheReadTokens": job.cache_read_tokens,
        "cacheCreationTokens": job.cache_creation_tokens,
        "costUsd": job.cost_usd,
        "entitiesCreated": job.entities_created,
        "entitiesModified": job.entities_modified,
        "relationshipsCreated": job.relationships_created,
        "relationshipsModified": job.relationships_modified,
        "writeOps": job.write_ops(),
        "instanceCount": len(job.target_instances),
        "fileCount": len(job.target_files),
        "assistantPreview": preview,
        "errorMessage": job.error_message,
    }


def serialize_job_detail(
    job: ExtractionJobRecord,
    *,
    settings: ExtractionWorkloadRuntimeSettings | None = None,
) -> dict[str, Any]:
    """Full job detail for watch dialog and drill-down panels."""
    runtime = settings or get_extraction_workload_runtime_settings()
    payload = serialize_recent_job(job, settings=runtime)
    workdir = job_workdir(
        knowledge_graph_id=job.knowledge_graph_id,
        job_id=job.job_id,
        settings=runtime,
    )
    payload.update(
        {
            "strategy": job.strategy,
            "description": job.description,
            "attempt": job.attempt,
            "targetInstances": [instance.to_dict() for instance in job.target_instances],
            "targetFiles": [target_file.to_dict() for target_file in job.target_files],
            "hasActivityLog": activity_log_path(workdir).is_file(),
        }
    )
    return payload
