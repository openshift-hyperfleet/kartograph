"""Unit tests for workload schema service mutation routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from graph.domain.value_objects import MutationOperationType
from infrastructure.extraction_workload.schema_service import GraphWorkloadSchemaService


@pytest.mark.asyncio
async def test_apply_mutation_jsonl_routes_instance_ops_to_graph_writer() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    mutation_writer = MagicMock()
    mutation_writer.apply_instance_operations = AsyncMock(
        return_value={"applied": True, "errors": [], "operations_applied": 1}
    )
    service = GraphWorkloadSchemaService(session=session, mutation_writer=mutation_writer)
    service._repository = MagicMock()
    service._repository.apply_mutation_log = AsyncMock()

    jsonl = (
        '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service",'
        '"set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap","source_path":"assistant"}}'
    )
    result = await service.apply_mutation_jsonl(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        jsonl=jsonl,
    )

    assert result["applied"] is True
    service._repository.apply_mutation_log.assert_not_called()
    mutation_writer.apply_instance_operations.assert_awaited_once()
    await_args = mutation_writer.apply_instance_operations.await_args
    assert await_args.kwargs["tenant_id"] == "tenant-1"
    assert await_args.kwargs["knowledge_graph_id"] == "kg-1"
    assert await_args.kwargs["operations"][0].op == MutationOperationType.CREATE


@pytest.mark.asyncio
async def test_apply_mutation_jsonl_routes_define_ops_to_canonical_repo() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    mutation_writer = MagicMock()
    mutation_writer.apply_instance_operations = AsyncMock()
    service = GraphWorkloadSchemaService(session=session, mutation_writer=mutation_writer)
    service._repository = MagicMock()
    service._repository.apply_mutation_log = AsyncMock()

    jsonl = (
        '{"op":"DEFINE","type":"node","label":"service","description":"Service",'
        '"required_properties":["name"]}'
    )
    result = await service.apply_mutation_jsonl(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        jsonl=jsonl,
    )

    assert result["applied"] is True
    service._repository.apply_mutation_log.assert_awaited_once()
    mutation_writer.apply_instance_operations.assert_not_called()
