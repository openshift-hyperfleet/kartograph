"""Unit tests for instance change record helpers."""

from __future__ import annotations

from extraction.domain.instance_change_record import (
    build_instance_change_record,
    instance_changes_to_jsonl,
    parse_instance_changes_jsonl,
    property_changes,
)


def test_property_changes_detects_added_modified_removed_fields() -> None:
    changes = property_changes(
        {"name": "old", "status": "ready"},
        {"name": "new", "owner": "team-a"},
    )
    assert {"key": "name", "before": "old", "after": "new"} in changes
    assert {"key": "owner", "before": None, "after": "team-a"} in changes
    assert {"key": "status", "before": "ready", "after": None} in changes


def test_build_instance_change_record_for_create() -> None:
    record = build_instance_change_record(
        op="CREATE",
        entity_kind="node",
        instance_id="service:abc",
        label="service",
        before=None,
        after={"name": "api", "slug": "api"},
    )
    assert record["before"] is None
    assert record["after"]["properties"]["slug"] == "api"
    assert record["property_changes"]


def test_instance_changes_jsonl_round_trip() -> None:
    record = build_instance_change_record(
        op="UPDATE",
        entity_kind="edge",
        instance_id="depends_on:abc",
        label="depends_on",
        before={"weight": 1},
        after={"weight": 2},
        start_id="service:a",
        end_id="service:b",
    )
    jsonl = instance_changes_to_jsonl([record])
    parsed = parse_instance_changes_jsonl(jsonl)
    assert parsed[0]["id"] == "depends_on:abc"
    assert parsed[0]["start_id"] == "service:a"
