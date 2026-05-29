"""Port for preparing sticky session containers before graph-management chat."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode


class IStickySessionRuntimeService(Protocol):
    """Starts sticky containers and streams transparent readiness progress."""

    async def stream_runtime_warmup(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
    ) -> AsyncIterator[dict[str, Any]]:
        ...

    async def ensure_runtime_for_chat(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
        ui_mode: GraphManagementUiMode,
        session: ExtractionAgentSession,
    ) -> AsyncIterator[dict[str, Any]]:
        ...
