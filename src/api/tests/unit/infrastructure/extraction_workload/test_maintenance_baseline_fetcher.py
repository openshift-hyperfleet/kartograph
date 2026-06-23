"""Unit tests for maintenance baseline GitHub content fetcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from infrastructure.extraction_workload.maintenance_baseline_fetcher import (
    MaintenanceBaselineContentFetcher,
)


@pytest.mark.asyncio
async def test_github_context_scopes_data_source_lookup_to_tenant() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result)

    fetcher = MaintenanceBaselineContentFetcher(session=session, tenant_id="tenant-a")
    with pytest.raises(ValueError, match="Data source not found"):
        await fetcher._github_context_for_source("ds-other-tenant")

    session.execute.assert_awaited_once()
    _statement, params = session.execute.await_args.args
    assert params == {"data_source_id": "ds-other-tenant", "tenant_id": "tenant-a"}
