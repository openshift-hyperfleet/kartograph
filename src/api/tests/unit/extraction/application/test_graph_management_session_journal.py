"""Unit tests for Graph Management session mutation journaling."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from extraction.application.graph_management_session_journal import (
    GraphManagementSessionJournalService,
    append_applied_jsonl_to_session,
)
from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.extraction_job import ExtractionJobStatus
from extraction.domain.value_objects import ExtractionSessionMode


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
    assert "Graph Management · Schema Design" in job.job_set_name
