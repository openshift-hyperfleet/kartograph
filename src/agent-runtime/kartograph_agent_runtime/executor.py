"""Turn execution for sticky session chat using Claude Agent SDK or fallback mode."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

from kartograph_agent_runtime.settings import AgentRuntimeSettings
from kartograph_agent_runtime.thinking_stream import (
    initial_sdk_thinking_lines,
    push_thinking,
    thinking_events_from_sdk_message,
)
from kartograph_agent_runtime.tools import RuntimeTooling
from kartograph_agent_runtime.vertex import build_claude_agent_env

_DEFAULT_TURN_TIMEOUT_SECONDS = 600.0
_SDK_HEARTBEAT_SECONDS = 8.0


def _build_system_prompt(
    agent_configuration: dict[str, Any],
    *,
    workspace_appendix: str = "",
) -> str:
    system_prompt = str(agent_configuration.get("system_prompt") or "").strip()
    guardrails = agent_configuration.get("guardrails") or []
    skills = agent_configuration.get("skills") or {}
    skill_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(skills.items()))
    guardrail_lines = "\n".join(f"- {item}" for item in guardrails if str(item).strip())
    sections = [
        section
        for section in (system_prompt, guardrail_lines, skill_lines, workspace_appendix.strip())
        if section
    ]
    return "\n\n".join(sections) or "You are the Graph Management Assistant."


def _build_workspace_prompt_appendix(settings: AgentRuntimeSettings) -> str:
    import json
    from pathlib import Path

    root = Path(settings.workspace_dir)
    index_path = root / "sources-index.json"
    if index_path.is_file():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            index = None
        sources = index.get("sources") if isinstance(index, dict) else None
        if isinstance(sources, list) and sources:
            lines = [
                "## Session workspace",
                f"Workspace mount: `{settings.workspace_dir}`",
                (
                    "Prepared repository files live under "
                    "`repository-files/<job_package_id>/` relative to the workspace mount. "
                    "Use Read, Grep, and Glob tools against those paths."
                ),
            ]
            for source in sources[:12]:
                if not isinstance(source, dict):
                    continue
                package_id = str(source.get("job_package_id") or "?")
                entry_count = source.get("entry_count", 0)
                repository_root = str(
                    source.get("repository_root") or f"repository-files/{package_id}"
                )
                data_source_id = str(source.get("data_source_id") or "?")
                lines.append(
                    f"- `{repository_root}`: {entry_count} file(s) "
                    f"(data source `{data_source_id}`)"
                )
                sample_paths = source.get("sample_paths")
                if isinstance(sample_paths, list):
                    for path in sample_paths[:6]:
                        if path:
                            lines.append(f"  - `{path}`")
            return "\n".join(lines)

    repo_root = root / "repository-files"
    if not repo_root.is_dir():
        return (
            f"## Session workspace\n"
            f"Workspace mount: `{settings.workspace_dir}`\n"
            "No prepared JobPackage repository files are materialized yet. "
            "Prepare data sources under Graph Management → Data sources."
        )

    package_dirs = sorted(path for path in repo_root.iterdir() if path.is_dir())
    if not package_dirs:
        return (
            f"## Session workspace\n"
            f"Workspace mount: `{settings.workspace_dir}`\n"
            "Prepared data sources exist, but repository files have not been extracted yet. "
            "Re-prepare data sources under Graph Management → Data sources."
        )

    lines = [
        "## Session workspace",
        f"Workspace mount: `{settings.workspace_dir}`",
        (
            "Prepared repository files live under "
            "`repository-files/<job_package_id>/` relative to the workspace mount. "
            "Use Read, Grep, and Glob tools against those paths."
        ),
    ]
    for package_dir in package_dirs[:8]:
        files = sorted(path for path in package_dir.rglob("*") if path.is_file())
        lines.append(f"- `{package_dir.name}`: {len(files)} file(s)")
        for file_path in files[:4]:
            rel = file_path.relative_to(package_dir).as_posix()
            lines.append(f"  - `{rel}`")
    return "\n".join(lines)


def _apply_model_env(settings: AgentRuntimeSettings) -> str:
    for key, value in build_claude_agent_env(settings).items():
        os.environ[key] = value
    if settings.vertex_enabled():
        return "Vertex AI"
    if settings.anthropic_api_key.strip():
        return "Anthropic API"
    return "unconfigured"


def _extract_sdk_reply(message: Any) -> str | None:
    result = getattr(message, "result", None)
    if isinstance(result, str) and result.strip():
        return result.strip()

    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        if parts:
            return parts[-1]
    return None


def _build_sdk_env(settings: AgentRuntimeSettings) -> dict[str, str]:
    env = build_claude_agent_env(settings)
    if settings.gcloud_config_dir.strip():
        env.setdefault("CLOUDSDK_CONFIG", settings.gcloud_config_dir.strip())
    if settings.google_application_credentials.strip():
        env.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS",
            settings.google_application_credentials.strip(),
        )
    env.setdefault("HOME", settings.home_dir.strip() or "/tmp")
    env.setdefault("API_TIMEOUT_MS", "120000")
    env.setdefault("CLAUDE_CODE_MAX_RETRIES", "2")
    env.setdefault("CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS", "120000")
    return env


def _timeout_error_message(
    *,
    settings: AgentRuntimeSettings,
    auth_mode: str,
    turn_timeout_seconds: float,
) -> str:
    parts = [
        f"Claude Agent SDK did not complete within {int(turn_timeout_seconds)}s.",
    ]
    if auth_mode == "Vertex AI":
        creds_path = settings.google_application_credentials.strip()
        creds_present = bool(creds_path)
        parts.append(
            "Vertex AI "
            f"project={settings.vertex_project_id.strip() or '(missing)'}, "
            f"region={settings.vertex_region.strip() or '(missing)'}, "
            f"ADC={'configured' if creds_present else 'missing'}."
        )
        if creds_present:
            from pathlib import Path

            creds_readable = Path(creds_path).is_file()
            parts.append(
                f"Credentials file {'readable' if creds_readable else 'not found'} at {creds_path}."
            )
    else:
        parts.append(
            "Direct Anthropic API "
            f"{'configured' if settings.anthropic_api_key.strip() else 'missing ANTHROPIC_API_KEY'}."
        )
    parts.append(
        "The model may still be running in the container — check sticky container logs "
        "for Vertex auth or quota errors."
    )
    return " ".join(parts)


async def stream_turn_events(
    *,
    settings: AgentRuntimeSettings,
    message: str,
    ui_mode: str,
    agent_configuration: dict[str, Any],
    message_history: list[dict[str, Any]],
    turn_timeout_seconds: float = _DEFAULT_TURN_TIMEOUT_SECONDS,
) -> AsyncIterator[dict[str, Any]]:
    auth_mode = _apply_model_env(settings)
    yield {
        "type": "thinking",
        "recent": [
            "Starting Claude Agent SDK runtime…",
            f"Model backend: {auth_mode}",
            f"Applying {ui_mode} skill overlay",
        ],
    }

    if settings.model_configured():
        async for event in _stream_with_claude_sdk(
            settings=settings,
            message=message,
            ui_mode=ui_mode,
            agent_configuration=agent_configuration,
            message_history=message_history,
            auth_mode=auth_mode,
            turn_timeout_seconds=turn_timeout_seconds,
        ):
            yield event
        return

    tooling = RuntimeTooling(settings=settings)
    skill_keys = ", ".join(sorted(agent_configuration.get("skills", {}).keys())[:4]) or "default"
    reply = (
        f"**Graph Management Assistant ({ui_mode})**\n\n"
        f"I received your message with skills: {skill_keys}.\n\n"
        f"> {message.strip()}\n\n"
        "Configure Vertex AI (`CLAUDE_CODE_USE_VERTEX=1`, `ANTHROPIC_VERTEX_PROJECT_ID`, "
        "`CLOUD_ML_REGION`) or `ANTHROPIC_API_KEY` to enable live model execution. "
        "Graph and mutation tools are wired via "
        f"`{settings.api_base_url}` using the injected workload token."
    )
    if message.lower().startswith("search graph:"):
        slug = message.split(":", 1)[1].strip()
        try:
            graph_result = await tooling.search_graph_by_slug(slug=slug)
            reply += f"\n\nGraph search returned {graph_result.get('count', 0)} node(s)."
        except Exception as exc:  # noqa: BLE001
            reply += f"\n\nGraph search failed: {exc}"
    yield {"type": "done", "ok": True, "reply": reply}


async def _stream_with_claude_sdk(
    *,
    settings: AgentRuntimeSettings,
    message: str,
    ui_mode: str,
    agent_configuration: dict[str, Any],
    message_history: list[dict[str, Any]],
    auth_mode: str,
    turn_timeout_seconds: float,
) -> AsyncIterator[dict[str, Any]]:
    from claude_agent_sdk import ClaudeAgentOptions, query

    system_prompt = _build_system_prompt(
        agent_configuration,
        workspace_appendix=_build_workspace_prompt_appendix(settings),
    )
    history_lines = [
        f"{entry.get('role', 'unknown')}: {entry.get('content', '')}"
        for entry in message_history[-6:]
        if isinstance(entry, dict)
    ]
    prompt = message
    if history_lines:
        prompt = "Recent conversation:\n" + "\n".join(history_lines) + f"\n\nUser: {message}"

    recent = initial_sdk_thinking_lines(auth_mode=auth_mode, ui_mode=ui_mode)
    yield {"type": "thinking", "recent": list(recent)}

    sdk_env = _build_sdk_env(settings)
    workspace_dir = settings.workspace_dir.strip() or "/workspace"
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        env=sdk_env,
        permission_mode="bypassPermissions",
        max_turns=8,
        setting_sources=[],
        cwd=workspace_dir,
        add_dirs=[workspace_dir],
    )

    reply: str | None = None
    reply_parts: list[str] = []
    last_compose_at = 0
    elapsed_seconds = 0
    try:
        async with asyncio.timeout(turn_timeout_seconds):
            sdk_iter = query(prompt=prompt, options=options).__aiter__()
            while True:
                try:
                    sdk_message = await asyncio.wait_for(
                        sdk_iter.__anext__(),
                        timeout=_SDK_HEARTBEAT_SECONDS,
                    )
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    elapsed_seconds += int(_SDK_HEARTBEAT_SECONDS)
                    heartbeat = push_thinking(
                        recent,
                        f"Waiting for model response… ({elapsed_seconds}s)",
                    )
                    if heartbeat:
                        yield heartbeat
                    continue

                thinking_events, last_compose_at = thinking_events_from_sdk_message(
                    sdk_message,
                    recent=recent,
                    reply_parts=reply_parts,
                    last_compose_at=last_compose_at,
                )
                for event in thinking_events:
                    yield event

                extracted = _extract_sdk_reply(sdk_message)
                if extracted:
                    reply = extracted
                elif reply_parts:
                    reply = "".join(reply_parts).strip() or None
    except TimeoutError:
        yield {
            "type": "done",
            "ok": False,
            "error": {
                "code": "AGENT_TURN_TIMEOUT",
                "message": _timeout_error_message(
                    settings=settings,
                    auth_mode=auth_mode,
                    turn_timeout_seconds=turn_timeout_seconds,
                ),
            },
        }
        return
    except Exception as exc:  # noqa: BLE001
        yield {
            "type": "done",
            "ok": False,
            "error": {
                "code": "AGENT_TURN_FAILED",
                "message": str(exc),
            },
        }
        return

    if not reply:
        reply = (
            "Claude Agent SDK completed without a textual response. "
            "Retry with a more specific graph-management request."
        )
    yield {"type": "done", "ok": True, "reply": reply}
