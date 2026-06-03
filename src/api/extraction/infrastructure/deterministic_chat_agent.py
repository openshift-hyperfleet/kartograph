"""Deterministic chat agent for tracer-bullet chat turn execution."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import GraphManagementUiMode


class DeterministicExtractionChatAgent:
    """Tracer-bullet agent that simulates thinking lines and a structured reply."""

    async def stream_turn(
        self,
        *,
        session: ExtractionAgentSession,
        user_message: str,
        ui_mode: GraphManagementUiMode,
        workload_token: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        yield {
            "type": "thinking",
            "recent": [
                "Starting sticky session Claude agent runtime…",
                f"Applying {ui_mode.value} skill overlay",
            ],
        }
        yield {
            "type": "thinking",
            "recent": [
                "Starting sticky session Claude agent runtime…",
                f"Applying {ui_mode.value} skill overlay",
                "Reviewing session message history",
            ],
        }
        skills = session.runtime_context.get("agent_configuration", {}).get("skills", {})
        skill_keys = ", ".join(sorted(skills.keys())[:3]) or "default skills"
        reply = (
            f"**Graph Management Assistant ({ui_mode.value})**\n\n"
            f"I received your message and loaded skills: {skill_keys}.\n\n"
            f"> {user_message.strip()}\n\n"
            "This is a tracer-bullet reply. The sticky container runtime will invoke "
            "the Claude Agent SDK with JobPackage context in a follow-up change."
        )
        yield {"type": "done", "ok": True, "reply": reply}
