"""Repository ports for Extraction sessions."""

from __future__ import annotations

from typing import Protocol

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.domain.value_objects import ExtractionSessionMode, ExtractionSessionRunMetric, GraphManagementUiMode


class IExtractionAgentSessionRepository(Protocol):
    """Persistence contract for extraction agent sessions."""

    async def save(self, session: ExtractionAgentSession) -> None: ...

    async def get_by_id(self, session_id: str) -> ExtractionAgentSession | None: ...

    async def get_active_by_id_for_scope(
        self,
        *,
        session_id: str,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> ExtractionAgentSession | None: ...

    async def find_active_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession | None: ...

    async def find_active_by_ui_mode(
        self,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession | None: ...

    async def list_active_by_user_and_kg(
        self,
        user_id: str,
        knowledge_graph_id: str,
    ) -> list[ExtractionAgentSession]: ...

    async def list_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode | None = None,
    ) -> list[ExtractionAgentSession]: ...


class IExtractionSessionRunMetricsReader(Protocol):
    """Read-only access to run-level metrics linked to extraction sessions."""

    async def find_metrics_by_session_ids(
        self,
        *,
        knowledge_graph_id: str,
        session_ids: list[str],
    ) -> dict[str, list[ExtractionSessionRunMetric]]: ...


class IExtractionSkillOverrideRepository(Protocol):
    """Read KG-specific skill override templates."""

    async def get_overrides_for_knowledge_graph(
        self,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> dict[str, str]: ...


class IGraphManagementSessionArchivalRepository(Protocol):
    """Persist archived Graph Management Assistant session write history."""

    async def insert_archived_session_job(self, job: ExtractionJobRecord) -> None: ...

