"""Unit tests for scanner_common helpers."""

from __future__ import annotations

from extraction.infrastructure.instance_generator_templates.scanner_common import (
    dedupe_instances,
    dedupe_relationships,
    generate_slug,
)


def test_generate_slug_normalizes_text() -> None:
    assert generate_slug("Basic Workflow Validation!") == "basic_workflow_validation"
    assert generate_slug("  Foo--Bar  ") == "foo_bar"


def test_dedupe_instances_keeps_first_slug() -> None:
    rows = [
        {"slug": "b", "properties": {}},
        {"slug": "a", "properties": {}},
        {"slug": "a", "properties": {"name": "dup"}},
    ]
    unique, skipped = dedupe_instances(rows)
    assert [row["slug"] for row in unique] == ["a", "b"]
    assert skipped == 1


def test_dedupe_relationships_keeps_first_pair() -> None:
    rows = [
        {"source_slug": "a", "target_slug": "b"},
        {"source_slug": "a", "target_slug": "b"},
        {"source_slug": "a", "target_slug": "c"},
    ]
    unique, skipped = dedupe_relationships(rows)
    assert len(unique) == 2
    assert skipped == 1
