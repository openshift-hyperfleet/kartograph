"""Unit tests for helpers/sync_instances.py bulk diff JSONL generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from extraction.infrastructure.extraction_job_helpers import sync_instances


def test_parse_current_nodes_accepts_list_api_response() -> None:
    payload = {
        "entity_type": "Adapter",
        "nodes": [
            {"id": "adapter:aaa", "slug": "keep-me", "properties": {"data_source_id": "ds-1"}},
            {"id": "adapter:bbb", "slug": "drop-me", "properties": {"data_source_id": "ds-1"}},
        ],
        "total": 2,
    }

    nodes = sync_instances.parse_current_nodes(payload)

    assert len(nodes) == 2
    assert nodes[0]["id"] == "adapter:aaa"


def test_parse_desired_slugs_accepts_slug_array() -> None:
    desired = sync_instances.parse_desired_instances(["keep-me", "new-one"])

    assert set(desired) == {"keep-me", "new-one"}
    assert desired["keep-me"]["properties"] == {}


def test_parse_desired_slugs_accepts_scanner_instances_array() -> None:
    payload = [
        {"slug": "keep-me", "properties": {"name": "Keep Me"}},
        {"slug": "new-one", "properties": {"name": "New One"}},
    ]

    desired = sync_instances.parse_desired_instances(payload)

    assert desired["keep-me"]["properties"]["name"] == "Keep Me"


def test_build_sync_mutations_emits_delete_for_extra_current_nodes() -> None:
    current = [
        {"id": "adapter:aaa", "slug": "keep-me", "properties": {}},
        {"id": "adapter:bbb", "slug": "drop-me", "properties": {}},
    ]
    desired = sync_instances.parse_desired_instances(["keep-me"])

    lines = sync_instances.build_sync_mutations(
        entity_type="Adapter",
        current_nodes=current,
        desired_by_slug=desired,
    )

    assert len(lines) == 1
    assert lines[0] == {"op": "DELETE", "type": "node", "id": "adapter:bbb"}


def test_build_sync_mutations_respects_data_source_filter() -> None:
    current = [
        {
            "id": "adapter:aaa",
            "slug": "drop-me",
            "properties": {"data_source_id": "hyperfleet-e2e"},
        },
        {
            "id": "adapter:bbb",
            "slug": "other-ds",
            "properties": {"data_source_id": "other"},
        },
    ]
    desired = sync_instances.parse_desired_instances([])

    lines = sync_instances.build_sync_mutations(
        entity_type="Adapter",
        current_nodes=current,
        desired_by_slug=desired,
        filter_data_source_id="hyperfleet-e2e",
    )

    assert lines == [{"op": "DELETE", "type": "node", "id": "adapter:aaa"}]


def test_build_sync_mutations_create_missing_adds_create_lines() -> None:
    current = [{"id": "adapter:aaa", "slug": "keep-me", "properties": {}}]
    desired = sync_instances.parse_desired_instances(
        [{"slug": "keep-me", "properties": {"name": "Keep Me"}}]
    )
    desired["new-one"] = {"properties": {"name": "New One", "transport": "maestro"}}

    lines = sync_instances.build_sync_mutations(
        entity_type="Adapter",
        current_nodes=current,
        desired_by_slug=desired,
        create_missing=True,
        data_source_id="hyperfleet-e2e",
    )

    assert len(lines) == 1
    create_line = lines[0]
    assert create_line["op"] == "CREATE"
    assert create_line["type"] == "node"
    assert create_line["label"] == "Adapter"
    assert create_line["set_properties"]["slug"] == "new-one"
    assert create_line["set_properties"]["data_source_id"] == "hyperfleet-e2e"


def test_build_sync_mutations_skips_create_when_slug_already_exists() -> None:
    current = [{"id": "adapter:aaa", "slug": "existing", "properties": {}}]
    desired = sync_instances.parse_desired_instances(["existing", "brand-new"])

    lines = sync_instances.build_sync_mutations(
        entity_type="Adapter",
        current_nodes=current,
        desired_by_slug=desired,
        create_missing=True,
        data_source_id="hyperfleet-e2e",
    )

    assert len(lines) == 1
    assert lines[0]["set_properties"]["slug"] == "brand-new"


def test_main_writes_jsonl_file(tmp_path: Path) -> None:
    current_path = tmp_path / "current.json"
    desired_path = tmp_path / "desired.json"
    out_path = tmp_path / "bulk.jsonl"
    current_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "adapter:aaa", "slug": "keep", "properties": {}},
                    {"id": "adapter:bbb", "slug": "drop", "properties": {}},
                ]
            }
        ),
        encoding="utf-8",
    )
    desired_path.write_text(json.dumps(["keep"]), encoding="utf-8")

    exit_code = sync_instances.main(
        [
            "--entity-type",
            "Adapter",
            "--current",
            str(current_path),
            "--desired",
            str(desired_path),
            "--out",
            str(out_path),
        ]
    )

    assert exit_code == 0
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == "adapter:bbb"


def test_main_requires_entity_type() -> None:
    with pytest.raises(SystemExit) as exc_info:
        sync_instances.main(["--current", "a.json", "--desired", "b.json"])
    assert exc_info.value.code != 0
