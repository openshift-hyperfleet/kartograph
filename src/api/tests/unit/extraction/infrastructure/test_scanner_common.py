"""Unit tests for scanner_common helpers."""

from __future__ import annotations

from extraction.infrastructure.instance_generator_templates.scanner_common import (
    dedupe_instances,
    dedupe_relationships,
    generate_slug,
    relationship_output_paths,
    relationship_scanner_stem,
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


def test_relationship_paths_use_underscore_stem() -> None:
    assert relationship_scanner_stem(
        source="ComponentTest",
        relationship="tests",
        target="APIEndpoint",
    ) == "ComponentTest_tests_APIEndpoint"
    json_path, jsonl_path = relationship_output_paths(
        source="ComponentTest",
        relationship="tests",
        target="APIEndpoint",
    )
    assert json_path == "instance_generators/out/ComponentTest_tests_APIEndpoint_instances.json"
    assert jsonl_path == "instance_generators/out/ComponentTest_tests_APIEndpoint_instances.jsonl"
    assert "|" not in json_path
