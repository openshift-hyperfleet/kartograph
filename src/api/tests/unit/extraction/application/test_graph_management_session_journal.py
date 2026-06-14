"""Unit tests for Graph Management session mutation journaling."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from extraction.application.graph_management_session_journal import (
    GraphManagementSessionJournalService,
    append_applied_jsonl_to_session,
    append_turn_usage_to_session,
)
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.extraction_job import ExtractionJobStatus
from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode


class _InMemorySessionRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, ExtractionAgentSession] = {}

    async def save(self, session: ExtractionAgentSession) -> None:
        self._by_id[session.id] = replace(session)

    async def get_by_id(self, session_id: str) -> ExtractionAgentSession | None:
        session = self._by_id.get(session_id)
        return replace(session) if session else None


class _InMemoryJobRepository:
    def __init__(self) -> None:
        self.inserted: list[object] = []

    async def insert_archived_session_job(self, job) -> None:
        self.inserted.append(job)


def test_append_applied_jsonl_to_session_accumulates_lines() -> None:
    session = ExtractionAgentSession(
        id="session-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
    )
    append_applied_jsonl_to_session(
        session,
        applied_jsonl='{"op":"CREATE","type":"node","id":"service:abc"}',
    )
    append_applied_jsonl_to_session(
        session,
        applied_jsonl='{"op":"DELETE","type":"node","id":"service:def"}',
    )

    journal = session.runtime_context["mutation_journal"]
    assert journal["line_count"] == 2
    assert "DELETE" in journal["jsonl"]


@pytest.mark.asyncio
async def test_archive_session_mutations_creates_archived_job() -> None:
    session_repo = _InMemorySessionRepository()
    job_repo = _InMemoryJobRepository()
    service = GraphManagementSessionJournalService(
        session_repository=session_repo,
        extraction_job_repository=job_repo,
    )
    session = ExtractionAgentSession(
        id="session-2",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
    )
    append_applied_jsonl_to_session(
        session,
        applied_jsonl=(
            '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service",'
            '"set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap"}}'
        ),
    )

    await service.archive_session_mutations(session)

    assert len(job_repo.inserted) == 1
    job = job_repo.inserted[0]
    assert job.status == ExtractionJobStatus.ARCHIVED
    assert job.job_id == "gma-session-2"
    assert job.strategy == "graph_management_session"
    assert job.applied_mutations_jsonl
    assert "Graph Management · Initial Schema Design" in job.job_set_name


def test_append_turn_usage_to_session_accumulates_tokens() -> None:
    session = ExtractionAgentSession(
        id="session-3",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
    )
    append_turn_usage_to_session(
        session,
        usage={
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 10,
            "cache_creation_tokens": 5,
            "cost_usd": 0.12,
        },
    )
    append_turn_usage_to_session(
        session,
        usage={
            "input_tokens": 200,
            "output_tokens": 75,
            "cost_usd": 0.08,
        },
    )

    journal = session.runtime_context["mutation_journal"]
    assert journal["input_tokens"] == 300
    assert journal["output_tokens"] == 125
    assert journal["cache_read_tokens"] == 10
    assert journal["cost_usd"] == pytest.approx(0.20)


@pytest.mark.asyncio
async def test_archive_session_mutations_includes_tokens_and_initial_schema_label() -> None:
    session_repo = _InMemorySessionRepository()
    job_repo = _InMemoryJobRepository()
    service = GraphManagementSessionJournalService(
        session_repository=session_repo,
        extraction_job_repository=job_repo,
    )
    session = ExtractionAgentSession(
        id="session-4",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
    )
    session.runtime_context["graph_management_ui_mode"] = (
        GraphManagementUiMode.INITIAL_SCHEMA_DESIGN.value
    )
    append_applied_jsonl_to_session(
        session,
        applied_jsonl=(
            '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service",'
            '"set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap"}}'
        ),
    )
    append_turn_usage_to_session(
        session,
        usage={
            "input_tokens": 1200,
            "output_tokens": 400,
            "cost_usd": 0.45,
        },
    )

    await service.archive_session_mutations(session)

    assert len(job_repo.inserted) == 1
    job = job_repo.inserted[0]
    assert job.input_tokens == 1200
    assert job.output_tokens == 400
    assert job.cost_usd == pytest.approx(0.45)
    assert job.job_set_name == "Graph Management · Initial Schema Design"


@pytest.mark.asyncio
async def test_archive_session_mutations_uses_one_off_mutations_job_set() -> None:
    session_repo = _InMemorySessionRepository()
    job_repo = _InMemoryJobRepository()
    service = GraphManagementSessionJournalService(
        session_repository=session_repo,
        extraction_job_repository=job_repo,
    )
    session = ExtractionAgentSession(
        id="session-6",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
    )
    session.runtime_context["graph_management_ui_mode"] = GraphManagementUiMode.ONE_OFF_MUTATIONS.value
    append_turn_usage_to_session(
        session,
        usage={"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.02},
    )

    await service.archive_session_mutations(session)

    assert len(job_repo.inserted) == 1
    assert job_repo.inserted[0].job_set_name == "Graph Management · One-off Mutations"


@pytest.mark.asyncio
async def test_archive_session_mutations_token_only_session() -> None:
    session_repo = _InMemorySessionRepository()
    job_repo = _InMemoryJobRepository()
    service = GraphManagementSessionJournalService(
        session_repository=session_repo,
        extraction_job_repository=job_repo,
    )
    session = ExtractionAgentSession(
        id="session-5",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode=ExtractionSessionMode.SCHEMA_BOOTSTRAP,
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
    )
    append_turn_usage_to_session(
        session,
        usage={"input_tokens": 500, "output_tokens": 100, "cost_usd": 0.05},
    )

    await service.archive_session_mutations(session)

    assert len(job_repo.inserted) == 1
    job = job_repo.inserted[0]
    assert job.input_tokens == 500
    assert job.applied_mutations_jsonl is None
