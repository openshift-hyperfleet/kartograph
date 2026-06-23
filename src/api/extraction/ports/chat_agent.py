"""Port contract for graph-management chat agent execution."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import GraphManagementUiMode


class IExtractionChatAgent(Protocol):
    """Runs one conversational turn inside a sticky session runtime."""

    def stream_turn(
        self,
        *,
        session: ExtractionAgentSession,
        user_message: str,
        ui_mode: GraphManagementUiMode,
        workload_token: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield NDJSON-style event dictionaries ending with a terminal done event."""
        ...
