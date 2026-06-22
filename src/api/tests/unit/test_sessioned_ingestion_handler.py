"""Unit tests for session-aware ingestion event context preparation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from shared_kernel.datasource_types import DataSourceAdapterType


def _make_session_factory(session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=ctx)
    return factory


def _make_data_source() -> DataSource:
    now = datetime.now(UTC)
    return DataSource(
        id=DataSourceId(value="01JTESTSESSIONHANDLERDATA00"),
        knowledge_graph_id="01JTESTSESSIONHANDLERKG0000",
        tenant_id="tenant-001",
        name="GitHub Source",
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"owner": "org", "repo": "repo", "branch": "main"},
        credentials_path="datasource/01JTESTSESSIONHANDLERDATA00/credentials",
        schedule=Schedule(schedule_type=ScheduleType.MANUAL),
        last_sync_at=None,
        created_at=now,
        updated_at=now,
        last_extraction_baseline_commit="baseline123",
    )


@pytest.mark.asyncio
async def test_sessioned_ingestion_handler_prepares_commit_context():
    """Wrapper should inject baseline/credentials and refresh tracked head."""
    from main import _SessionedIngestionEventHandler

    session = AsyncMock()
    session_factory = _make_session_factory(session)
    handler = _SessionedIngestionEventHandler(session_factory=session_factory)
    handler._resolve_github_tracked_head_commit = AsyncMock(return_value="head456")  # type: ignore[attr-defined]

    outbox_repo = MagicMock()
    ds_repo = MagicMock()
    secret_store = MagicMock()
    ingestion_handler = MagicMock()
    ingestion_handler.handle = AsyncMock()
    ingestion_service = MagicMock()

    data_source = _make_data_source()
    ds_repo.get_by_id = AsyncMock(return_value=data_source)
    ds_repo.save = AsyncMock()
    secret_store.retrieve = AsyncMock(return_value={"token": "tok"})

    payload = {
        "sync_run_id": "run-001",
        "data_source_id": data_source.id.value,
        "knowledge_graph_id": data_source.knowledge_graph_id,
        "tenant_id": data_source.tenant_id,
        "adapter_type": "github",
        "connection_config": data_source.connection_config,
        "credentials_path": data_source.credentials_path,
    }

    management_settings = MagicMock()
    management_settings.encryption_key.get_secret_value.return_value = (
        "WlAwWU83a2hSODl2SVY4MHBzQWpwaDBSUHhOU3NfQ3R6aXpvNTJfNE5odz0="
    )

    with (
        patch(
            "infrastructure.outbox.repository.OutboxRepository",
            return_value=outbox_repo,
        ),
        patch(
            "management.infrastructure.repositories.data_source_repository.DataSourceRepository",
            return_value=ds_repo,
        ),
        patch(
            "management.infrastructure.repositories.fernet_secret_store.FernetSecretStore",
            return_value=secret_store,
        ),
        patch(
            "ingestion.application.services.ingestion_service.IngestionService",
            return_value=ingestion_service,
        ),
        patch(
            "ingestion.infrastructure.event_handler.IngestionEventHandler",
            return_value=ingestion_handler,
        ),
        patch("main.get_management_settings", return_value=management_settings),
    ):
        await handler.handle("SyncStarted", payload)

    ingestion_handler.handle.assert_called_once()
    call_payload = ingestion_handler.handle.call_args.args[1]
    assert call_payload["baseline_commit"] == "baseline123"
    assert call_payload["tracked_branch_head_commit"] == "head456"
    assert "credentials" not in call_payload
    assert ingestion_handler.handle.call_args.kwargs["runtime_credentials"] == {
        "token": "tok"
    }
    ds_repo.save.assert_awaited_once()
    assert data_source.tracked_branch_head_commit == "head456"


@pytest.mark.asyncio
async def test_sessioned_ingestion_handler_sets_no_changes_flag_when_heads_match():
    """Wrapper should short-circuit when tracked head equals baseline."""
    from main import _SessionedIngestionEventHandler

    session = AsyncMock()
    session_factory = _make_session_factory(session)
    handler = _SessionedIngestionEventHandler(session_factory=session_factory)
    handler._resolve_github_tracked_head_commit = AsyncMock(return_value="baseline123")  # type: ignore[attr-defined]

    outbox_repo = MagicMock()
    ds_repo = MagicMock()
    secret_store = MagicMock()
    ingestion_handler = MagicMock()
    ingestion_handler.handle = AsyncMock()
    ingestion_service = MagicMock()

    data_source = _make_data_source()
    ds_repo.get_by_id = AsyncMock(return_value=data_source)
    ds_repo.save = AsyncMock()
    secret_store.retrieve = AsyncMock(return_value={"token": "tok"})

    payload = {
        "sync_run_id": "run-002",
        "data_source_id": data_source.id.value,
        "knowledge_graph_id": data_source.knowledge_graph_id,
        "tenant_id": data_source.tenant_id,
        "adapter_type": "github",
        "connection_config": data_source.connection_config,
        "credentials_path": data_source.credentials_path,
    }

    management_settings = MagicMock()
    management_settings.encryption_key.get_secret_value.return_value = (
        "WlAwWU83a2hSODl2SVY4MHBzQWpwaDBSUHhOU3NfQ3R6aXpvNTJfNE5odz0="
    )

    with (
        patch(
            "infrastructure.outbox.repository.OutboxRepository",
            return_value=outbox_repo,
        ),
        patch(
            "management.infrastructure.repositories.data_source_repository.DataSourceRepository",
            return_value=ds_repo,
        ),
        patch(
            "management.infrastructure.repositories.fernet_secret_store.FernetSecretStore",
            return_value=secret_store,
        ),
        patch(
            "ingestion.application.services.ingestion_service.IngestionService",
            return_value=ingestion_service,
        ),
        patch(
            "ingestion.infrastructure.event_handler.IngestionEventHandler",
            return_value=ingestion_handler,
        ),
        patch("main.get_management_settings", return_value=management_settings),
    ):
        await handler.handle("SyncStarted", payload)

    call_payload = ingestion_handler.handle.call_args.args[1]
    assert call_payload["baseline_commit"] == "baseline123"
    assert call_payload["tracked_branch_head_commit"] == "baseline123"
    assert call_payload["no_changes_detected"] is True
    assert "credentials" not in call_payload
    assert ingestion_handler.handle.call_args.kwargs["runtime_credentials"] == {
        "token": "tok"
    }


@pytest.mark.asyncio
async def test_sessioned_ingestion_handler_uses_last_prepared_for_ingest_only():
    """ingest_only runs should compare against last prepared commit, not extraction baseline."""
    from main import _SessionedIngestionEventHandler

    session = AsyncMock()
    session_factory = _make_session_factory(session)
    handler = _SessionedIngestionEventHandler(session_factory=session_factory)
    handler._resolve_github_tracked_head_commit = AsyncMock(return_value="prepared123")  # type: ignore[attr-defined]
    handler._ingest_only_archive_available = AsyncMock(return_value=True)  # type: ignore[attr-defined]

    outbox_repo = MagicMock()
    ds_repo = MagicMock()
    secret_store = MagicMock()
    ingestion_handler = MagicMock()
    ingestion_handler.handle = AsyncMock()
    ingestion_service = MagicMock()

    data_source = _make_data_source()
    data_source.last_prepared_commit = "prepared123"
    ds_repo.get_by_id = AsyncMock(return_value=data_source)
    ds_repo.save = AsyncMock()
    secret_store.retrieve = AsyncMock(return_value={"token": "tok"})

    payload = {
        "sync_run_id": "run-003",
        "data_source_id": data_source.id.value,
        "knowledge_graph_id": data_source.knowledge_graph_id,
        "tenant_id": data_source.tenant_id,
        "adapter_type": "github",
        "connection_config": data_source.connection_config,
        "credentials_path": data_source.credentials_path,
        "pipeline_mode": "ingest_only",
    }

    management_settings = MagicMock()
    management_settings.encryption_key.get_secret_value.return_value = (
        "WlAwWU83a2hSODl2SVY4MHBzQWpwaDBSUHhOU3NfQ3R6aXpvNTJfNE5odz0="
    )

    with (
        patch(
            "infrastructure.outbox.repository.OutboxRepository",
            return_value=outbox_repo,
        ),
        patch(
            "management.infrastructure.repositories.data_source_repository.DataSourceRepository",
            return_value=ds_repo,
        ),
        patch(
            "management.infrastructure.repositories.fernet_secret_store.FernetSecretStore",
            return_value=secret_store,
        ),
        patch(
            "ingestion.application.services.ingestion_service.IngestionService",
            return_value=ingestion_service,
        ),
        patch(
            "ingestion.infrastructure.event_handler.IngestionEventHandler",
            return_value=ingestion_handler,
        ),
        patch("main.get_management_settings", return_value=management_settings),
    ):
        await handler.handle("SyncStarted", payload)

    call_payload = ingestion_handler.handle.call_args.args[1]
    assert call_payload["baseline_commit"] == "prepared123"
    assert call_payload["no_changes_detected"] is True


@pytest.mark.asyncio
async def test_sessioned_ingestion_handler_runs_ingest_only_when_archive_missing():
    """ingest_only at branch head should still run when the JobPackage ZIP was lost."""
    from main import _SessionedIngestionEventHandler

    session = AsyncMock()
    session_factory = _make_session_factory(session)
    handler = _SessionedIngestionEventHandler(session_factory=session_factory)
    handler._resolve_github_tracked_head_commit = AsyncMock(return_value="prepared123")  # type: ignore[attr-defined]
    handler._ingest_only_archive_available = AsyncMock(return_value=False)  # type: ignore[attr-defined]

    outbox_repo = MagicMock()
    ds_repo = MagicMock()
    secret_store = MagicMock()
    ingestion_handler = MagicMock()
    ingestion_handler.handle = AsyncMock()
    ingestion_service = MagicMock()

    ds = _make_data_source()
    ds.last_prepared_commit = "prepared123"
    ds_repo.get_by_id = AsyncMock(return_value=ds)
    ds_repo.save = AsyncMock()
    secret_store.retrieve = AsyncMock(return_value={"token": "tok"})

    payload = {
        "sync_run_id": "run-004",
        "data_source_id": ds.id.value,
        "knowledge_graph_id": ds.knowledge_graph_id,
        "tenant_id": ds.tenant_id,
        "adapter_type": "github",
        "connection_config": ds.connection_config,
        "credentials_path": ds.credentials_path,
        "pipeline_mode": "ingest_only",
    }

    management_settings = MagicMock()
    management_settings.encryption_key.get_secret_value.return_value = (
        "WlAwWU83a2hSODl2SVY4MHBzQWpwaDBSUHhOU3NfQ3R6aXpvNTJfNE5odz0="
    )

    with (
        patch(
            "infrastructure.outbox.repository.OutboxRepository",
            return_value=outbox_repo,
        ),
        patch(
            "management.infrastructure.repositories.data_source_repository.DataSourceRepository",
            return_value=ds_repo,
        ),
        patch(
            "management.infrastructure.repositories.fernet_secret_store.FernetSecretStore",
            return_value=secret_store,
        ),
        patch(
            "ingestion.application.services.ingestion_service.IngestionService",
            return_value=ingestion_service,
        ),
        patch(
            "ingestion.infrastructure.event_handler.IngestionEventHandler",
            return_value=ingestion_handler,
        ),
        patch("main.get_management_settings", return_value=management_settings),
    ):
        await handler.handle("SyncStarted", payload)

    call_payload = ingestion_handler.handle.call_args.args[1]
    assert call_payload["baseline_commit"] == "prepared123"
    assert "no_changes_detected" not in call_payload
