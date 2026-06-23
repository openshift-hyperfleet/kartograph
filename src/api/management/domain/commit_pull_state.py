"""Git pull-style commit state for Git-backed data sources.

``tracked_branch_head_commit`` is the remote branch tip (what ``git pull`` would
fast-forward to). ``clone_head_commit`` / ``last_prepared_commit`` record what
we have ingested locally. ``newest_unpulled_commit`` is the branch tip when it
differs from what we have — the newest commit on the branch we do not have yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from management.domain.aggregates import DataSource


def resolve_ingested_head_commit(data_source: DataSource) -> str | None:
    """Commit whose content we have ingested (local HEAD after pull/prepare)."""
    return data_source.clone_head_commit or data_source.last_prepared_commit


def resolve_newest_unpulled_commit(data_source: DataSource) -> str | None:
    """Newest commit on the tracked branch that we do not have yet, if any."""
    remote_tip = data_source.tracked_branch_head_commit
    if not remote_tip:
        return None
    ingested = resolve_ingested_head_commit(data_source)
    if not ingested:
        return remote_tip
    if ingested == remote_tip:
        return None
    return remote_tip


def has_unpulled_commits(data_source: DataSource) -> bool:
    """True when the remote branch tip is ahead of our ingested head."""
    return resolve_newest_unpulled_commit(data_source) is not None
