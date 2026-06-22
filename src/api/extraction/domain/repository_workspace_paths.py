"""Filesystem-safe folder names for sticky session repository materialization."""

from __future__ import annotations

import re

_UNSAFE_CHARS = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")


def repository_folder_for_data_source(*, name: str, data_source_id: str) -> str:
    """Derive a stable, human-readable directory name for one data source."""
    slug = _UNSAFE_CHARS.sub("-", name.strip().lower()).strip("-")
    slug = _MULTI_DASH.sub("-", slug)
    if slug:
        return slug
    fallback = _UNSAFE_CHARS.sub("-", data_source_id.strip().lower()).strip("-")
    return fallback or "data-source"
