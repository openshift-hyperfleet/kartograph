"""Unit tests for extraction session history with run-level metrics."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.value_objects import (
    ExtractionSessionMode,
    ExtractionSessionRunMetric,
    GraphManagementUiMode,
)
from extraction.domain.value_objects import ExtractionSessionMode as Mode


class _InMemoryAgentSessionRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, ExtractionAgentSession] = {}

    async def save(self, session: ExtractionAgentSession) -> None:
        self._by_id[session.id] = replace(session)

    async def get_by_id(self, session_id: str) -> ExtractionAgentSession | None:
        session = self._by_id.get(session_id)
        return replace(session) if session else None

    async def find_active_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession | None:
        for session in self._by_id.values():
            if (
                session.user_id == user_id
                and session.knowledge_graph_id == knowledge_graph_id
                and session.mode == mode
                and session.archived_at is None
            ):
                return replace(session)
        return None

    async def find_active_by_ui_mode(
        self,
        user_id: str,
        knowledge_graph_id: str,
        ui_mode: GraphManagementUiMode,
    ) -> ExtractionAgentSession | None:
        for session in self._by_id.values():
            if (
                session.user_id == user_id
                and session.knowledge_graph_id == knowledge_graph_id
                and session.graph_management_ui_mode == ui_mode
                and session.archived_at is None
            ):
                return replace(session)
        return None

    async def list_active_by_user_and_kg(
        self,
        user_id: str,
        knowledge_graph_id: str,
    ) -> list[ExtractionAgentSession]:
        return [
            replace(session)
            for session in self._by_id.values()
            if session.user_id == user_id
            and session.knowledge_graph_id == knowledge_graph_id
            and session.archived_at is None
        ]

    async def list_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode | None = None,
    ) -> list[ExtractionAgentSession]:
        sessions = [
            replace(session)
            for session in self._by_id.values()
            if session.user_id == user_id
            and session.knowledge_graph_id == knowledge_graph_id
            and (mode is None or session.mode == mode)
        ]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)


class _InMemoryRunMetricsReader:
    def __init__(self) -> None:
        self._metrics: dict[str, list[ExtractionSessionRunMetric]] = {}

    def seed(self, session_id: str, metric: ExtractionSessionRunMetric) -> None:
        self._metrics.setdefault(session_id, []).append(metric)

    async def find_metrics_by_session_ids(
        self,
        *,
        knowledge_graph_id: str,
        session_ids: list[str],
    ) -> dict[str, list[ExtractionSessionRunMetric]]:
        del knowledge_graph_id
        return {
            session_id: list(self._metrics.get(session_id, []))
            for session_id in session_ids
        }


@pytest.mark.asyncio
class TestExtractionSessionHistoryService:
    async def test_list_session_history_includes_archived_sessions_with_metrics(self):
        repo = _InMemoryAgentSessionRepository()
        metrics_reader = _InMemoryRunMetricsReader()
        service = ExtractionAgentSessionService(
            repository=repo,
            run_metrics_reader=metrics_reader,
        )

        archived = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        archived.message_history = [{"role": "user", "content": "hello"}]
        archived.updated_at = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
        await repo.save(archived)
        metrics_reader.seed(
            archived.id,
            ExtractionSessionRunMetric(
                sync_run_id="run-1",
                mutation_log_id="mlog-1",
                status="completed",
                started_at=datetime(2026, 5, 20, 11, 0, tzinfo=UTC),
                completed_at=datetime(2026, 5, 20, 11, 30, tzinfo=UTC),
                token_usage_total=512,
                cost_total_usd=0.42,
                operation_counts={"create_node": 3},
            ),
        )

        await service.clear_chat(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        history = await service.list_session_history(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=Mode.EXTRACTION_OPERATIONS,
        )

        assert len(history) == 2
        archived_record = next(
            item for item in history if item.session.archived_at is not None
        )
        assert archived_record.session.id == archived.id
        assert archived_record.session.updated_at is not None
        assert archived_record.session.archived_at is not None
        assert len(archived_record.run_metrics) == 1
        assert archived_record.run_metrics[0].mutation_log_id == "mlog-1"
        assert archived_record.run_metrics[0].token_usage_total == 512

    async def test_clear_chat_retains_archived_sessions_for_history(self):
        repo = _InMemoryAgentSessionRepository()
        metrics_reader = _InMemoryRunMetricsReader()
        service = ExtractionAgentSessionService(
            repository=repo,
            run_metrics_reader=metrics_reader,
        )

        first = await service.start_session(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        await service.clear_chat(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )
        await service.clear_chat(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            ui_mode=GraphManagementUiMode.EXTRACTION_JOBS,
        )

        history = await service.list_session_history(
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode=Mode.EXTRACTION_OPERATIONS,
        )

        assert len(history) == 3
        assert any(
            item.session.id == first.id and item.session.archived_at is not None
            for item in history
        )
        assert sum(1 for item in history if item.session.archived_at is None) == 1
