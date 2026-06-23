"""PostgreSQL reader for extraction session run metrics."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.domain.value_objects import ExtractionSessionRunMetric
from extraction.ports.repositories import IExtractionSessionRunMetricsReader


class ExtractionSessionRunMetricsReader(IExtractionSessionRunMetricsReader):
    """Resolve sync-run metrics for extraction sessions without Management imports."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_metrics_by_session_ids(
        self,
        *,
        knowledge_graph_id: str,
        session_ids: list[str],
    ) -> dict[str, list[ExtractionSessionRunMetric]]:
        if not session_ids:
            return {}

        stmt = text(
            """
            SELECT
                sr.id AS sync_run_id,
                sr.status,
                sr.started_at,
                sr.completed_at,
                sr.mutation_log_run
            FROM data_source_sync_runs sr
            JOIN data_sources ds ON ds.id = sr.data_source_id
            WHERE ds.knowledge_graph_id = :knowledge_graph_id
              AND sr.mutation_log_run IS NOT NULL
              AND sr.mutation_log_run->>'session_id' = ANY(:session_ids)
            ORDER BY sr.started_at DESC
            """
        )
        result = await self._session.execute(
            stmt,
            {
                "knowledge_graph_id": knowledge_graph_id,
                "session_ids": session_ids,
            },
        )

        metrics_by_session: dict[str, list[ExtractionSessionRunMetric]] = {
            session_id: [] for session_id in session_ids
        }
        for row in result.mappings().all():
            payload = row["mutation_log_run"] or {}
            session_id = payload.get("session_id")
            if session_id not in metrics_by_session:
                continue
            metrics_by_session[session_id].append(
                ExtractionSessionRunMetric(
                    sync_run_id=row["sync_run_id"],
                    mutation_log_id=payload.get("mutation_log_id"),
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    token_usage_total=(
                        int(payload["token_usage_total"])
                        if payload.get("token_usage_total") is not None
                        else None
                    ),
                    cost_total_usd=(
                        float(payload["cost_total_usd"])
                        if payload.get("cost_total_usd") is not None
                        else None
                    ),
                    operation_counts={
                        str(key): int(value)
                        for key, value in (
                            payload.get("operation_counts") or {}
                        ).items()
                    },
                )
            )
        return metrics_by_session
