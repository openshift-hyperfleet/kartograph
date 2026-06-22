"""Shared helpers for entity and relationship scanner scripts."""

from __future__ import annotations

import re
from typing import Any

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def generate_slug(name: str) -> str:
    """Build a stable slug from arbitrary source text.

    Rules:
    - Lowercase ASCII
    - Non-alphanumeric runs become single underscores
    - No leading or trailing underscores
    """
    slug = _SLUG_PATTERN.sub("_", name.strip().lower())
    return slug.strip("_")


def dedupe_instances(
    instances: list[dict[str, Any]],
    *,
    slug_key: str = "slug",
) -> tuple[list[dict[str, Any]], int]:
    """Drop duplicate slugs, keeping the first occurrence deterministically."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    skipped = 0
    for row in sorted(instances, key=lambda item: str(item.get(slug_key, ""))):
        slug = str(row.get(slug_key) or "").strip()
        if not slug or slug in seen:
            skipped += 1
            continue
        seen.add(slug)
        unique.append(row)
    return unique, skipped


def relationship_scanner_stem(*, source: str, relationship: str, target: str) -> str:
    """Filesystem-safe stem for relationship scanner and output files."""
    return f"{source}_{relationship}_{target}"


def relationship_output_paths(
    *, source: str, relationship: str, target: str
) -> tuple[str, str]:
    """Return workspace-relative JSON and JSONL output paths for one relationship type."""
    stem = relationship_scanner_stem(
        source=source,
        relationship=relationship,
        target=target,
    )
    return (
        f"instance_generators/out/{stem}_instances.json",
        f"instance_generators/out/{stem}_instances.jsonl",
    )


def dedupe_relationships(
    relationships: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Drop duplicate (source_slug, target_slug) pairs, keeping first occurrence."""
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    skipped = 0
    for row in sorted(
        relationships,
        key=lambda item: (
            str(item.get("source_slug") or ""),
            str(item.get("target_slug") or ""),
        ),
    ):
        source = str(row.get("source_slug") or "").strip()
        target = str(row.get("target_slug") or "").strip()
        if not source or not target:
            skipped += 1
            continue
        key = (source, target)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        unique.append(row)
    return unique, skipped
