"""Repository ports for Extraction sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.domain.local_runtime import (
    LocalRuntimeAgentPresence,
    LocalRuntimeWorkKind,
    LocalRuntimeWorkRequest,
)
from extraction.domain.value_objects import (
    ExtractionSessionMode,
    ExtractionSessionRunMetric,
    GraphManagementUiMode,
)


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


class ILocalRuntimeRepository(Protocol):
    """Persistence contract for local-runtime Sandbox execution work requests.

    See specs/extraction/local-sandbox-execution.spec.md. Application services
    depend on this port, not on the concrete
    `extraction.infrastructure.repositories.local_runtime_repository` module,
    to keep the application layer free of infrastructure imports (enforced by
    `tests/unit/extraction/test_architecture.py`).
    """

    async def commit(self) -> None: ...

    async def record_presence(self, *, user_id: str, tenant_id: str) -> None: ...

    async def get_presence(
        self, *, user_id: str
    ) -> LocalRuntimeAgentPresence | None: ...

    async def enqueue_work_request(
        self,
        *,
        tenant_id: str,
        user_id: str,
        knowledge_graph_id: str,
        kind: LocalRuntimeWorkKind,
        session_id: str | None = None,
        job_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> LocalRuntimeWorkRequest: ...

    async def claim_next_pending(
        self, *, user_id: str
    ) -> LocalRuntimeWorkRequest | None: ...

    async def record_heartbeat(self, *, request_id: str, user_id: str) -> bool: ...

    async def mark_completed(
        self, *, request_id: str, user_id: str, result: dict[str, Any] | None = None
    ) -> bool: ...

    async def mark_failed(
        self, *, request_id: str, user_id: str, failure_reason: str
    ) -> bool: ...

    async def get_by_id(
        self, *, request_id: str, user_id: str
    ) -> LocalRuntimeWorkRequest | None: ...

    async def fail_timed_out_pending(
        self, *, older_than: datetime, failure_reason: str
    ) -> int: ...

    async def fail_stale_claims(
        self, *, older_than: datetime, failure_reason: str
    ) -> int: ...
