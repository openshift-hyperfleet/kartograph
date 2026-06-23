"""Unit tests for git pull-style commit state helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from management.domain.aggregates import DataSource
from management.domain.commit_pull_state import (
    has_unpulled_commits,
    resolve_ingested_head_commit,
    resolve_newest_unpulled_commit,
)
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from shared_kernel.datasource_types import DataSourceAdapterType


def _ds(**overrides) -> DataSource:
    now = datetime.now(UTC)
    base = dict(
        id=DataSourceId(value="01JTESTCOMMITPULLSTATE000"),
        knowledge_graph_id="kg-001",
        tenant_id="tenant-001",
        name="repo",
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"owner": "o", "repo": "r", "branch": "main"},
        credentials_path=None,
        schedule=Schedule(schedule_type=ScheduleType.MANUAL),
        last_sync_at=None,
        created_at=now,
        updated_at=now,
        clone_head_commit=None,
        last_prepared_commit=None,
        tracked_branch_head_commit=None,
    )
    base.update(overrides)
    return DataSource(**base)


class TestCommitPullState:
    def test_ingested_head_prefers_clone_over_prepared(self):
        ds = _ds(clone_head_commit="clone-sha", last_prepared_commit="prep-sha")
        assert resolve_ingested_head_commit(ds) == "clone-sha"

    def test_newest_unpulled_is_remote_tip_when_never_ingested(self):
        ds = _ds(tracked_branch_head_commit="remote-tip")
        assert resolve_newest_unpulled_commit(ds) == "remote-tip"
        assert has_unpulled_commits(ds) is True

    def test_newest_unpulled_none_when_up_to_date(self):
        ds = _ds(
            clone_head_commit="same-sha",
            tracked_branch_head_commit="same-sha",
        )
        assert resolve_newest_unpulled_commit(ds) is None
        assert has_unpulled_commits(ds) is False

    def test_newest_unpulled_is_branch_tip_when_behind(self):
        ds = _ds(
            clone_head_commit="old-sha",
            tracked_branch_head_commit="new-tip",
        )
        assert resolve_newest_unpulled_commit(ds) == "new-tip"
        assert has_unpulled_commits(ds) is True
