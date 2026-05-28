"""SyncLifecycleHandler: updates sync run status based on lifecycle events.

This handler implements the event-driven state machine defined in the sync
lifecycle spec. It processes all lifecycle events and updates the
DataSourceSyncRun entity to reflect the current state.

State machine transitions:
  SyncStarted              → ingesting
  JobPackageProduced       → ai_extracting
  IngestionFailed          → failed (with error)
  MutationLogProduced      → applying
  ExtractionFailed         → failed (with error)
  IngestionPrepared        → ingested (ingestion context ready; no extraction)
  MutationsApplied         → completed (DataSource.last_sync_at updated)
  MutationApplicationFailed → failed (with error)

Terminal states (ingested, completed, failed) cannot be transitioned further.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from management.domain.entities import MutationLogRunMetadata
from management.domain.value_objects import DataSourceId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from management.ports.repositories import (
        IDataSourceRepository,
        IDataSourceSyncRunRepository,
    )

# Events that transition the run to 'failed' — carry an 'error' payload field.
_FAILURE_EVENTS = frozenset(
    {"IngestionFailed", "ExtractionFailed", "MutationApplicationFailed"}
)

# Mapping from event type to new status (for non-failure events)
_STATUS_MAP: dict[str, str] = {
    "SyncStarted": "ingesting",
    "JobPackageProduced": "ai_extracting",
    "MutationLogProduced": "applying",
    "MutationsApplied": "completed",
    "IngestionPrepared": "ingested",
}

_SUPPORTED_EVENTS = frozenset(_STATUS_MAP.keys()) | _FAILURE_EVENTS


class SyncLifecycleHandler:
    """Handles all sync lifecycle events and updates sync run status.

    This handler is registered in the CompositeEventHandler and processes
    events from multiple bounded contexts (Management, Ingestion, Extraction,
    Graph). Its sole responsibility is keeping the DataSourceSyncRun status
    up-to-date.

    For 'MutationsApplied', it additionally updates DataSource.last_sync_at
    to record when the last successful sync completed.
    """

    def __init__(
        self,
        session: "AsyncSession",
        sync_run_repository: "IDataSourceSyncRunRepository",
        data_source_repository: "IDataSourceRepository",
    ) -> None:
        """Initialize the sync lifecycle handler.

        Args:
            session: Database session for transaction management
            sync_run_repository: Repository for reading/updating sync runs
            data_source_repository: Repository for updating DataSource.last_sync_at
        """
        self._session = session
        self._sync_run_repo = sync_run_repository
        self._ds_repo = data_source_repository

    def supported_event_types(self) -> frozenset[str]:
        """Return all lifecycle event types handled by this handler."""
        return _SUPPORTED_EVENTS

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Process a lifecycle event and update sync run status.

        This method is idempotent: if the sync run is already in a terminal
        state (completed or failed) it is silently ignored. If the sync run
        is not found, the event is also silently ignored to allow for
        safe re-delivery.

        Args:
            event_type: One of the supported lifecycle event types
            payload: Event payload containing at minimum 'sync_run_id'
        """
        sync_run_id = payload.get("sync_run_id")
        if not sync_run_id:
            return

        sync_run = await self._sync_run_repo.get_by_id(sync_run_id)
        if sync_run is None:
            # Sync run not found — idempotent no-op
            return

        if sync_run.is_terminal():
            # Terminal states cannot be transitioned further
            return

        now = datetime.now(UTC)

        if event_type in _FAILURE_EVENTS:
            error_msg = payload.get("error", "Unknown error")
            sync_run.status = "failed"
            sync_run.error = error_msg
            sync_run.completed_at = now
            sync_run.logs.append(f"[{now.isoformat()}] {event_type}: {error_msg}")

        elif event_type == "IngestionPrepared":
            sync_run.status = "ingested"
            sync_run.completed_at = now
            job_package_id = payload.get("job_package_id")
            if job_package_id:
                sync_run.logs.append(
                    f"[{now.isoformat()}] Ingestion context prepared "
                    f"(job_package_id={job_package_id})"
                )
            elif payload.get("no_changes_detected") is True:
                sync_run.logs.append(
                    f"[{now.isoformat()}] No source changes detected; "
                    "ingestion context preparation skipped."
                )
            else:
                sync_run.logs.append(
                    f"[{now.isoformat()}] Ingestion context prepared for later extraction."
                )

        elif event_type == "MutationsApplied":
            sync_run.status = "completed"
            sync_run.completed_at = now
            sync_run.logs.append(f"[{now.isoformat()}] Sync completed")
            if payload.get("no_changes_detected") is True:
                sync_run.logs.append(
                    f"[{now.isoformat()}] No source changes were detected; "
                    "heavy extraction was short-circuited."
                )
            if sync_run.mutation_log_run is not None:
                sync_run.mutation_log_run.completed_at = now
                if payload.get("token_usage_total") is not None:
                    sync_run.mutation_log_run.token_usage_total = int(
                        payload["token_usage_total"]
                    )
                if payload.get("cost_total_usd") is not None:
                    sync_run.mutation_log_run.cost_total_usd = float(
                        payload["cost_total_usd"]
                    )
                if payload.get("operation_counts") is not None:
                    sync_run.mutation_log_run.operation_counts = {
                        str(k): int(v)
                        for k, v in dict(payload["operation_counts"]).items()
                    }
            await self._update_data_source_last_sync_at(
                data_source_id=sync_run.data_source_id,
                now=now,
            )

        else:
            new_status = _STATUS_MAP.get(event_type)
            if new_status is None:
                return
            sync_run.status = new_status
            sync_run.logs.append(
                f"[{now.isoformat()}] {event_type}: status → {new_status}"
            )
            if event_type == "MutationLogProduced":
                sync_run.mutation_log_run = MutationLogRunMetadata(
                    mutation_log_id=str(payload["mutation_log_id"]),
                    knowledge_graph_id=str(payload["knowledge_graph_id"]),
                    session_id=(
                        str(payload["session_id"])
                        if payload.get("session_id") is not None
                        else None
                    ),
                    actor_id=(
                        str(payload["actor_id"])
                        if payload.get("actor_id") is not None
                        else None
                    ),
                    started_at=now,
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
                        str(k): int(v)
                        for k, v in dict(payload.get("operation_counts") or {}).items()
                    },
                )

        await self._sync_run_repo.save(sync_run)
        await self._session.commit()

    async def _update_data_source_last_sync_at(
        self,
        data_source_id: str,
        now: datetime,
    ) -> None:
        """Update DataSource.last_sync_at after a successful sync.

        Args:
            data_source_id: The data source to update
            now: The timestamp to set as last_sync_at
        """
        ds = await self._ds_repo.get_by_id(DataSourceId(value=data_source_id))
        if ds is None:
            return

        ds.record_sync_completed()
        ds.advance_extraction_baseline_to_tracked_head()
        await self._ds_repo.save(ds)
