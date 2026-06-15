"""Tests for KG-scoped extraction baseline advancement."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from management.infrastructure.extraction_baseline_updater import (
    advance_extraction_baselines_for_knowledge_graph,
)
from shared_kernel.datasource_types import DataSourceAdapterType


def _make_ds(*, ds_id: str = "ds-001", kg_id: str = "kg-001", **kwargs) -> DataSource:
    now = datetime.now(UTC)
    defaults = {
        "id": DataSourceId(value=ds_id),
        "knowledge_graph_id": kg_id,
        "tenant_id": "tenant-001",
        "name": f"Source {ds_id}",
        "adapter_type": DataSourceAdapterType.GITHUB,
        "connection_config": {},
        "credentials_path": None,
        "schedule": Schedule(schedule_type=ScheduleType.MANUAL),
        "last_sync_at": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(kwargs)
    return DataSource(**defaults)


@pytest.mark.asyncio
async def test_advance_extraction_baselines_updates_all_sources_on_kg() -> None:
    ds_a = _make_ds(
        ds_id="ds-a",
        last_extraction_baseline_commit="old-a",
        last_prepared_commit="prepared-a",
    )
    ds_b = _make_ds(
        ds_id="ds-b",
        last_extraction_baseline_commit=None,
        clone_head_commit="prepared-b",
    )
    mock_repo = AsyncMock()
    mock_repo.find_by_knowledge_graph.return_value = [ds_a, ds_b]

    updated = await advance_extraction_baselines_for_knowledge_graph(
        session=AsyncMock(),
        knowledge_graph_id="kg-001",
        data_source_repository=mock_repo,
    )

    assert updated == 2
    assert ds_a.last_extraction_baseline_commit == "prepared-a"
    assert ds_b.last_extraction_baseline_commit == "prepared-b"
    assert mock_repo.save.await_count == 2


@pytest.mark.asyncio
async def test_advance_extraction_baselines_skips_sources_without_ingested_head() -> None:
    ds = _make_ds(last_extraction_baseline_commit="keep-me")
    mock_repo = AsyncMock()
    mock_repo.find_by_knowledge_graph.return_value = [ds]

    updated = await advance_extraction_baselines_for_knowledge_graph(
        session=AsyncMock(),
        knowledge_graph_id="kg-001",
        data_source_repository=mock_repo,
    )

    assert updated == 0
    assert ds.last_extraction_baseline_commit == "keep-me"
    mock_repo.save.assert_not_awaited()
