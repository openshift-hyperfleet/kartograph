"""Turn execution for sticky session chat using Claude Agent SDK or fallback mode."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from kartograph_agent_runtime.settings import AgentRuntimeSettings
from kartograph_agent_runtime.tools import RuntimeTooling
from kartograph_agent_runtime.vertex import build_claude_agent_env


def _build_system_prompt(agent_configuration: dict[str, Any]) -> str:
    system_prompt = str(agent_configuration.get("system_prompt") or "").strip()
    guardrails = agent_configuration.get("guardrails") or []
    skills = agent_configuration.get("skills") or {}
    skill_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(skills.items()))
    guardrail_lines = "\n".join(f"- {item}" for item in guardrails if str(item).strip())
    sections = [section for section in (system_prompt, guardrail_lines, skill_lines) if section]
    return "\n\n".join(sections) or "You are the Graph Management Assistant."


def _apply_model_env(settings: AgentRuntimeSettings) -> str:
    for key, value in build_claude_agent_env(settings).items():
        os.environ[key] = value
    if settings.vertex_enabled():
        return "Vertex AI"
    if settings.anthropic_api_key.strip():
        return "Anthropic API"
    return "unconfigured"


async def stream_turn_events(
    *,
    settings: AgentRuntimeSettings,
    message: str,
    ui_mode: str,
    agent_configuration: dict[str, Any],
    message_history: list[dict[str, Any]],
) -> AsyncIterator[dict[str, Any]]:
    auth_mode = _apply_model_env(settings)
    yield {
        "type": "thinking",
        "recent": [
            "Starting Claude Agent SDK runtime…",
            f"Model backend: {auth_mode}",
            f"Applying {ui_mode} skill overlay",
            f"Workspace mounted at {settings.workspace_dir}",
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
) -> AsyncIterator[dict[str, Any]]:
    from claude_agent_sdk import ClaudeAgentOptions, query

    system_prompt = _build_system_prompt(agent_configuration)
    history_lines = [
        f"{entry.get('role', 'unknown')}: {entry.get('content', '')}"
        for entry in message_history[-6:]
        if isinstance(entry, dict)
    ]
    prompt = message
    if history_lines:
        prompt = "Recent conversation:\n" + "\n".join(history_lines) + f"\n\nUser: {message}"

    yield {
        "type": "thinking",
        "recent": [
            f"Claude Agent SDK query started ({auth_mode})…",
            f"Mode overlay: {ui_mode}",
            "Tools: graph read enclave, mutation emitter",
        ],
    }

    chunks: list[str] = []
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        env=build_claude_agent_env(settings),
    )
    async for sdk_message in query(prompt=prompt, options=options):
        text = getattr(sdk_message, "result", None) or getattr(sdk_message, "content", None)
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())

    reply = chunks[-1] if chunks else (
        "Claude Agent SDK completed without a textual response. "
        "Retry with a more specific graph-management request."
    )
    yield {"type": "done", "ok": True, "reply": reply}
