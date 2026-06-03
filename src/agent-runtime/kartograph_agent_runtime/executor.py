"""Turn execution for sticky session chat using Claude Agent SDK or fallback mode."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator
from typing import Any

from kartograph_agent_runtime.agent_prompt import build_agent_system_prompt
from kartograph_agent_runtime.settings import AgentRuntimeSettings
from kartograph_agent_runtime.thinking_stream import (
    initial_sdk_thinking_lines,
    push_thinking,
    replace_last_thinking,
    thinking_events_from_sdk_message,
)
from kartograph_agent_runtime.tools import RuntimeTooling
from kartograph_agent_runtime.vertex import build_claude_agent_env

_DEFAULT_TURN_TIMEOUT_SECONDS = 1000.0
_SDK_HEARTBEAT_SECONDS = 8.0


def _build_system_prompt(
    agent_configuration: dict[str, Any],
    *,
    settings: AgentRuntimeSettings | None = None,
    workspace_appendix: str = "",
    workspace_readiness: dict[str, Any] | None = None,
) -> str:
    return build_agent_system_prompt(
        agent_configuration,
        settings=settings,
        workspace_appendix=workspace_appendix,
        workspace_readiness=workspace_readiness,
    )


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
                    "`repository-files/<data_source_name>/` relative to the workspace mount "
                    "(one folder per data source for this session's knowledge graph; folder "
                    "names are slugified data source names such as `hyperfleet-api`). "
                    "Use Read, Grep, and Glob tools against those paths."
                ),
            ]
            for source in sources[:12]:
                if not isinstance(source, dict):
                    continue
                data_source_name = str(source.get("data_source_name") or "?")
                data_source_id = str(source.get("data_source_id") or "?")
                entry_count = source.get("entry_count", 0)
                repository_folder = str(source.get("repository_folder") or "").strip()
                repository_root = str(
                    source.get("repository_root")
                    or (
                        f"repository-files/{repository_folder}"
                        if repository_folder
                        else f"repository-files/{data_source_name}"
                    )
                )
                package_id = str(source.get("job_package_id") or "?")
                lines.append(
                    f"- `{repository_root}`: {entry_count} file(s) "
                    f"(data source `{data_source_name}`, id `{data_source_id}`, "
                    f"JobPackage `{package_id}`)"
                )
                sample_paths = source.get("sample_paths")
                if isinstance(sample_paths, list):
                    for path in sample_paths[:6]:
                        if path:
                            lines.append(f"  - `{path}`")
                extension_counts = source.get("file_extension_counts")
                if isinstance(extension_counts, dict) and extension_counts:
                    top_extensions = sorted(
                        extension_counts.items(),
                        key=lambda item: (-int(item[1]), str(item[0])),
                    )[:8]
                    summary = ", ".join(f"{ext}={count}" for ext, count in top_extensions)
                    lines.append(f"  - extensions: {summary}")
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
            "`repository-files/<data_source_name>/` relative to the workspace mount "
            "(one folder per data source; names are slugified data source names). "
            "Use Read, Grep, and Glob tools against those paths."
        ),
    ]
    for package_dir in package_dirs[:8]:
        files = sorted(path for path in package_dir.rglob("*") if path.is_file())
        lines.append(f"- `repository-files/{package_dir.name}`: {len(files)} file(s)")
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

    structured = getattr(message, "structured_output", None)
    if structured is not None:
        if isinstance(structured, str) and structured.strip():
            return structured.strip()
        try:
            return json.dumps(structured, indent=2)
        except TypeError:
            return str(structured)

    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text)
        if parts:
            return "".join(parts).strip()
    return None


def finalize_sdk_turn_reply(
    *,
    reply: str | None,
    reply_parts: list[str],
    last_result: Any | None,
    notification_summaries: list[str],
) -> str | None:
    """Build the best available assistant reply after an SDK turn completes."""
    if isinstance(reply, str) and reply.strip():
        return reply.strip()

    streamed = "".join(reply_parts).strip()
    if streamed:
        return streamed

    if last_result is not None:
        extracted = _extract_sdk_reply(last_result)
        if extracted:
            return extracted

    if notification_summaries:
        return notification_summaries[-1]

    num_turns = int(getattr(last_result, "num_turns", 0) or 0)
    if num_turns > 0:
        return (
            f"**Assistant completed** ({num_turns} turn(s))\n\n"
            "The agent finished tool work without a final written reply. "
            "Review workspace artifacts or graph mutations, or ask the assistant "
            "to summarize what it changed."
        )

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


async def _iter_sdk_messages_with_heartbeat(
    sdk_iter: AsyncIterator[Any],
    *,
    heartbeat_seconds: float,
) -> AsyncIterator[Any | None]:
    """Yield SDK messages, or ``None`` when a heartbeat tick is due.

    Unlike ``asyncio.wait_for`` on ``__anext__()``, this never cancels a pending
    SDK read — cancelling mid-stream drops messages and prevents ResultMessage delivery.
    """
    pending = asyncio.create_task(sdk_iter.__anext__())
    try:
        while True:
            done, _ = await asyncio.wait(
                {pending},
                timeout=heartbeat_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if pending in done:
                try:
                    yield pending.result()
                except StopAsyncIteration:
                    return
                pending = asyncio.create_task(sdk_iter.__anext__())
            else:
                yield None
    finally:
        if not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending


def _tooling_settings(
    settings: AgentRuntimeSettings,
    workload_token: str | None = None,
) -> AgentRuntimeSettings:
    token = (workload_token or "").strip()
    if not token:
        return settings
    return settings.model_copy(update={"workload_token": token})


async def stream_turn_events(
    *,
    settings: AgentRuntimeSettings,
    message: str,
    ui_mode: str,
    agent_configuration: dict[str, Any],
    message_history: list[dict[str, Any]],
    turn_timeout_seconds: float = _DEFAULT_TURN_TIMEOUT_SECONDS,
    workload_token: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    effective_settings = _tooling_settings(settings, workload_token)
    auth_mode = _apply_model_env(effective_settings)
    yield {
        "type": "thinking",
        "recent": [
            "Starting Claude Agent SDK runtime…",
            f"Model backend: {auth_mode}",
            f"Applying {ui_mode} skill overlay",
        ],
    }

    if effective_settings.model_configured():
        async for event in _stream_with_claude_sdk(
            settings=effective_settings,
            message=message,
            ui_mode=ui_mode,
            agent_configuration=agent_configuration,
            message_history=message_history,
            auth_mode=auth_mode,
            turn_timeout_seconds=turn_timeout_seconds,
        ):
            yield event
        return

    tooling = RuntimeTooling(settings=effective_settings)
    skill_keys = ", ".join(sorted(agent_configuration.get("skills", {}).keys())[:4]) or "default"
    reply = (
        f"**Graph Management Assistant ({ui_mode})**\n\n"
        f"I received your message with skills: {skill_keys}.\n\n"
        f"> {message.strip()}\n\n"
        "Configure Vertex AI (`CLAUDE_CODE_USE_VERTEX=1`, `ANTHROPIC_VERTEX_PROJECT_ID`, "
        "`CLOUD_ML_REGION`) or `ANTHROPIC_API_KEY` to enable live model execution. "
        "Graph and mutation tools are wired via "
        f"`{effective_settings.api_base_url}` using the injected workload token."
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
    from claude_agent_sdk.types import ResultMessage, TaskNotificationMessage

    workspace_dir = settings.workspace_dir.strip() or "/workspace"
    tooling = RuntimeTooling(settings=settings)
    workspace_readiness: dict[str, Any] | None = None
    if settings.workload_token.strip():
        try:
            workspace_readiness = await tooling.get_workspace_readiness()
        except Exception:  # noqa: BLE001
            workspace_readiness = None

    system_prompt = _build_system_prompt(
        agent_configuration,
        settings=settings,
        workspace_appendix=_build_workspace_prompt_appendix(settings),
        workspace_readiness=workspace_readiness,
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
    options_kwargs: dict[str, Any] = {}
    if settings.workload_token.strip():
        from kartograph_agent_runtime.schema_tools import (
            GMA_ALLOWED_TOOL_NAMES,
            build_kartograph_schema_mcp_server,
        )

        options_kwargs["mcp_servers"] = {
            "kartograph": build_kartograph_schema_mcp_server(tooling),
        }
        options_kwargs["allowed_tools"] = list(GMA_ALLOWED_TOOL_NAMES)
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        env=sdk_env,
        permission_mode="bypassPermissions",
        max_turns=settings.max_turns,
        setting_sources=[],
        cwd=workspace_dir,
        add_dirs=[workspace_dir],
        **options_kwargs,
    )

    reply: str | None = None
    reply_parts: list[str] = []
    notification_summaries: list[str] = []
    last_result: ResultMessage | None = None
    last_compose_at = 0
    elapsed_seconds = 0
    try:
        async with asyncio.timeout(turn_timeout_seconds):
            sdk_iter = query(prompt=prompt, options=options).__aiter__()
            async for sdk_message in _iter_sdk_messages_with_heartbeat(
                sdk_iter,
                heartbeat_seconds=_SDK_HEARTBEAT_SECONDS,
            ):
                if sdk_message is None:
                    elapsed_seconds += int(_SDK_HEARTBEAT_SECONDS)
                    heartbeat = replace_last_thinking(
                        recent,
                        f"Waiting for model response… ({elapsed_seconds}s)",
                        prefix="Waiting for model response",
                    )
                    if heartbeat:
                        yield heartbeat
                        await asyncio.sleep(0)
                    continue

                thinking_events, last_compose_at = thinking_events_from_sdk_message(
                    sdk_message,
                    recent=recent,
                    reply_parts=reply_parts,
                    last_compose_at=last_compose_at,
                )
                for event in thinking_events:
                    yield event
                    await asyncio.sleep(0)

                if isinstance(sdk_message, TaskNotificationMessage):
                    summary = str(sdk_message.summary or "").strip()
                    if summary:
                        notification_summaries.append(summary)

                if isinstance(sdk_message, ResultMessage):
                    if sdk_message.is_error:
                        error_text = str(sdk_message.result or "").strip()
                        if not error_text and sdk_message.errors:
                            error_text = "; ".join(str(item) for item in sdk_message.errors)
                        if error_text:
                            error_thinking = push_thinking(recent, f"Error · {error_text}")
                            if error_thinking:
                                yield error_thinking
                                await asyncio.sleep(0)
                        yield {
                            "type": "done",
                            "ok": False,
                            "error": {
                                "code": "AGENT_SDK_ERROR",
                                "message": error_text or "Claude Agent SDK returned an error.",
                            },
                        }
                        return
                    last_result = sdk_message

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

    reply = finalize_sdk_turn_reply(
        reply=reply,
        reply_parts=reply_parts,
        last_result=last_result,
        notification_summaries=notification_summaries,
    )
    if not reply:
        yield {
            "type": "done",
            "ok": False,
            "error": {
                "code": "AGENT_NO_TEXTUAL_REPLY",
                "message": (
                    "The Graph Management Assistant finished without a reply. "
                    "Check sticky container logs for SDK output, then retry."
                ),
            },
        }
        return
    yield {"type": "done", "ok": True, "reply": reply}
