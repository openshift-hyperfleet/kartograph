"""Accumulate Graph Management Assistant mutations and archive on session end."""

from __future__ import annotations

from datetime import UTC, datetime

from ulid import ULID

from extraction.domain.entities.agent_session import ExtractionAgentSession
from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionJobStatus
from extraction.domain.value_objects import ExtractionSessionMode, GraphManagementUiMode
from extraction.domain.mutation_jsonl_metrics import metrics_from_mutation_jsonl
from extraction.ports.repositories import (
    IExtractionAgentSessionRepository,
    IGraphManagementSessionArchivalRepository,
)

GRAPH_MANAGEMENT_SESSION_STRATEGY = "graph_management_session"

_JOB_SET_BY_UI_MODE: dict[str, str] = {
    GraphManagementUiMode.INITIAL_SCHEMA_DESIGN.value: (
        "Graph Management · Initial Schema Design"
    ),
    GraphManagementUiMode.EXTRACTION_JOBS.value: "Graph Management · Extraction Jobs",
    GraphManagementUiMode.ONE_OFF_MUTATIONS.value: "Graph Management · One-off Mutations",
}

_DEFAULT_UI_MODE_BY_SESSION_MODE: dict[ExtractionSessionMode, GraphManagementUiMode] = {
    ExtractionSessionMode.SCHEMA_BOOTSTRAP: GraphManagementUiMode.INITIAL_SCHEMA_DESIGN,
    ExtractionSessionMode.EXTRACTION_OPERATIONS: GraphManagementUiMode.EXTRACTION_JOBS,
}

_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
)


def _ensure_journal(session: ExtractionAgentSession) -> dict[str, object]:
    journal = dict(session.runtime_context.get("mutation_journal") or {})
    if not journal.get("started_at"):
        journal["started_at"] = session.created_at.isoformat()
    return journal


def _journal_token_total(journal: dict[str, object]) -> int:
    return int(journal.get("input_tokens") or 0) + int(journal.get("output_tokens") or 0)


def _job_set_name_for_session(session: ExtractionAgentSession) -> str:
    if session.graph_management_ui_mode is not None:
        return _JOB_SET_BY_UI_MODE[session.graph_management_ui_mode.value]
    ui_mode = str(session.runtime_context.get("graph_management_ui_mode") or "")
    if ui_mode in _JOB_SET_BY_UI_MODE:
        return _JOB_SET_BY_UI_MODE[ui_mode]
    default_ui_mode = _DEFAULT_UI_MODE_BY_SESSION_MODE.get(session.mode)
    if default_ui_mode is not None:
        return _JOB_SET_BY_UI_MODE[default_ui_mode.value]
    return _JOB_SET_BY_UI_MODE[GraphManagementUiMode.INITIAL_SCHEMA_DESIGN.value]


def append_applied_jsonl_to_session(
    session: ExtractionAgentSession,
    *,
    applied_jsonl: str,
) -> None:
    """Append successfully applied mutation lines to the session journal."""
    chunk = applied_jsonl.strip()
    if not chunk:
        return
    journal = _ensure_journal(session)
    previous = str(journal.get("jsonl") or "").strip()
    combined = "\n".join(part for part in (previous, chunk) if part)
    journal["jsonl"] = combined
    journal["line_count"] = sum(1 for line in combined.splitlines() if line.strip())
    session.runtime_context["mutation_journal"] = journal


def append_instance_changes_to_session(
    session: ExtractionAgentSession,
    *,
    instance_changes_jsonl: str,
) -> None:
    chunk = instance_changes_jsonl.strip()
    if not chunk:
        return
    journal = _ensure_journal(session)
    previous = str(journal.get("instance_changes_jsonl") or "").strip()
    combined = "\n".join(part for part in (previous, chunk) if part)
    journal["instance_changes_jsonl"] = combined
    session.runtime_context["mutation_journal"] = journal


def append_turn_usage_to_session(
    session: ExtractionAgentSession,
    *,
    usage: dict[str, object],
) -> None:
    """Accumulate token usage from one Graph Management Assistant chat turn."""
    if not usage:
        return
    journal = _ensure_journal(session)
    for key in _USAGE_KEYS:
        journal[key] = int(journal.get(key) or 0) + int(usage.get(key) or 0)
    journal["cost_usd"] = float(journal.get("cost_usd") or 0.0) + float(usage.get("cost_usd") or 0.0)
    session.runtime_context["mutation_journal"] = journal


class GraphManagementSessionJournalService:
    """Persist per-session mutation JSONL and archive as one extraction job."""

    def __init__(
        self,
        *,
        session_repository: IExtractionAgentSessionRepository,
        extraction_job_repository: IGraphManagementSessionArchivalRepository,
    ) -> None:
        self._session_repository = session_repository
        self._extraction_job_repository = extraction_job_repository

    async def append_applied_jsonl(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        session_id: str,
        applied_jsonl: str,
    ) -> None:
        session = await self._session_repository.get_active_by_id_for_scope(
            session_id=session_id,
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        if session is None:
            return
        append_applied_jsonl_to_session(session, applied_jsonl=applied_jsonl)
        await self._session_repository.save(session)

    async def append_instance_changes(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        session_id: str,
        instance_changes_jsonl: str,
    ) -> None:
        session = await self._session_repository.get_active_by_id_for_scope(
            session_id=session_id,
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
        )
        if session is None:
            return
        append_instance_changes_to_session(
            session,
            instance_changes_jsonl=instance_changes_jsonl,
        )
        await self._session_repository.save(session)

    async def archive_session_mutations(self, session: ExtractionAgentSession) -> None:
        """Write one ARCHIVED extraction job row for the full GMA session."""
        journal = session.runtime_context.get("mutation_journal") or {}
        jsonl = str(journal.get("jsonl") or "").strip()
        instance_changes_jsonl = str(journal.get("instance_changes_jsonl") or "").strip()
        metrics = metrics_from_mutation_jsonl(jsonl) if jsonl else {}
        write_ops = int(metrics.get("write_ops") or 0)
        if write_ops <= 0:
            return

        now = datetime.now(UTC)
        started_at = session.created_at
        started_raw = journal.get("started_at")
        if isinstance(started_raw, str):
            try:
                started_at = datetime.fromisoformat(started_raw)
            except ValueError:
                started_at = session.created_at

        record = ExtractionJobRecord(
            id=str(ULID()),
            knowledge_graph_id=session.knowledge_graph_id,
            job_id=f"gma-{session.id}",
            job_set_name=_job_set_name_for_session(session),
            strategy=GRAPH_MANAGEMENT_SESSION_STRATEGY,
            status=ExtractionJobStatus.ARCHIVED,
            order_index=0,
            description=(
                f"Graph Management Assistant session {session.id} "
                f"({session.mode.value.replace('_', ' ')})"
            ),
            run_started_at=started_at,
            started_at=started_at,
            completed_at=now,
            archived_at=now,
            applied_mutations_jsonl=jsonl or None,
            applied_instance_changes_jsonl=instance_changes_jsonl or None,
            input_tokens=int(journal.get("input_tokens") or 0),
            output_tokens=int(journal.get("output_tokens") or 0),
            cache_read_tokens=int(journal.get("cache_read_tokens") or 0),
            cache_creation_tokens=int(journal.get("cache_creation_tokens") or 0),
            cost_usd=float(journal.get("cost_usd") or 0.0),
            entities_created=int(metrics.get("entities_created") or 0),
            entities_modified=int(metrics.get("entities_modified") or 0),
            relationships_created=int(metrics.get("relationships_created") or 0),
            relationships_modified=int(metrics.get("relationships_modified") or 0),
        )
        await self._extraction_job_repository.insert_archived_session_job(record)
