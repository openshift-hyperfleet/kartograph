"""Repository ports for Extraction sessions."""

from __future__ import annotations

from typing import Protocol

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import ExtractionSessionMode


class IExtractionAgentSessionRepository(Protocol):
    """Persistence contract for extraction agent sessions."""

    async def save(self, session: ExtractionAgentSession) -> None: ...

    async def get_by_id(self, session_id: str) -> ExtractionAgentSession | None: ...

    async def find_active_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession | None: ...

    async def list_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode | None = None,
    ) -> list[ExtractionAgentSession]: ...

