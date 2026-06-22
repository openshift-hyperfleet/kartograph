"""Unit tests for workload mutation preflight validation."""

from __future__ import annotations

import pytest

from graph.domain.value_objects import EntityType
from infrastructure.extraction_workload.mutation_preflight import validate_mutation_jsonl


class _FakeGraphReader:
    def __init__(self, *, existing_node_ids: frozenset[str] = frozenset()) -> None:
        self._existing_node_ids = existing_node_ids

    async def find_existing_node_ids(self, **kwargs) -> frozenset[str]:
        return self._existing_node_ids

    async def find_existing_edge_ids(self, **kwargs) -> frozenset[str]:
        return frozenset()

    async def find_existing_slugs_for_entity_type(self, **kwargs) -> frozenset[str]:
        return frozenset()


@pytest.mark.asyncio
async def test_validate_rejects_define_for_existing_type() -> None:
    jsonl = (
        '{"op":"DEFINE","type":"node","label":"service","description":"x",'
        '"required_properties":["name"]}'
    )
    errors = await validate_mutation_jsonl(
        jsonl_content=jsonl,
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        graph_reader=None,
        existing_type_keys=frozenset({("service", EntityType.NODE.value)}),
    )
    assert any("DEFINE" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_rejects_delete_for_missing_node_id() -> None:
    jsonl = '{"op":"DELETE","type":"node","id":"service:0123456789abcdef"}'
    reader = _FakeGraphReader(existing_node_ids=frozenset())
    errors = await validate_mutation_jsonl(
        jsonl_content=jsonl,
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        graph_reader=reader,
        existing_type_keys=frozenset(),
    )
    assert any("does not exist" in error and "DELETE" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_allows_delete_for_existing_node_id() -> None:
    jsonl = '{"op":"DELETE","type":"node","id":"service:0123456789abcdef"}'
    reader = _FakeGraphReader(existing_node_ids=frozenset({"service:0123456789abcdef"}))
    errors = await validate_mutation_jsonl(
        jsonl_content=jsonl,
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        graph_reader=reader,
        existing_type_keys=frozenset(),
    )
    assert errors == []


@pytest.mark.asyncio
async def test_validate_rejects_create_for_existing_node_id() -> None:
    jsonl = (
        '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service",'
        '"set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap","source_path":"assistant"}}'
    )
    reader = _FakeGraphReader(existing_node_ids=frozenset({"service:0123456789abcdef"}))
    errors = await validate_mutation_jsonl(
        jsonl_content=jsonl,
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        graph_reader=reader,
        existing_type_keys=frozenset(),
    )
    assert any("already exists" in error and "UPDATE" in error for error in errors)
