"""Capture before/after graph instance snapshots for applied mutation batches."""

from __future__ import annotations

from graph.domain.value_objects import EntityType, MutationOperation, MutationOperationType
from extraction.domain.instance_change_record import build_instance_change_record
from extraction.ports.workload_graph import IWorkloadGraphReader, WorkloadGraphNode, WorkloadGraphRelationship

_INSTANCE_OPS = frozenset(
    {
        MutationOperationType.CREATE,
        MutationOperationType.UPDATE,
        MutationOperationType.DELETE,
    }
)


async def capture_before_snapshots(
    *,
    tenant_id: str,
    knowledge_graph_id: str,
    operations: list[MutationOperation],
    graph_reader: IWorkloadGraphReader,
) -> tuple[dict[str, WorkloadGraphNode], dict[str, WorkloadGraphRelationship]]:
    node_ids = _collect_ids(operations, EntityType.NODE, include_create=False)
    edge_ids = _collect_ids(operations, EntityType.EDGE, include_create=False)
    nodes = await graph_reader.fetch_nodes_by_ids(
        tenant_id=tenant_id,
        knowledge_graph_id=knowledge_graph_id,
        node_ids=node_ids,
    )
    edges = await graph_reader.fetch_edges_by_ids(
        tenant_id=tenant_id,
        knowledge_graph_id=knowledge_graph_id,
        edge_ids=edge_ids,
    )
    return nodes, edges


async def capture_after_snapshots(
    *,
    tenant_id: str,
    knowledge_graph_id: str,
    operations: list[MutationOperation],
    graph_reader: IWorkloadGraphReader,
) -> tuple[dict[str, WorkloadGraphNode], dict[str, WorkloadGraphRelationship]]:
    node_ids = _collect_ids(operations, EntityType.NODE, include_delete=False)
    edge_ids = _collect_ids(operations, EntityType.EDGE, include_delete=False)
    nodes = await graph_reader.fetch_nodes_by_ids(
        tenant_id=tenant_id,
        knowledge_graph_id=knowledge_graph_id,
        node_ids=node_ids,
    )
    edges = await graph_reader.fetch_edges_by_ids(
        tenant_id=tenant_id,
        knowledge_graph_id=knowledge_graph_id,
        edge_ids=edge_ids,
    )
    return nodes, edges


def build_instance_change_records(
    *,
    operations: list[MutationOperation],
    nodes_before: dict[str, WorkloadGraphNode],
    edges_before: dict[str, WorkloadGraphRelationship],
    nodes_after: dict[str, WorkloadGraphNode],
    edges_after: dict[str, WorkloadGraphRelationship],
) -> list[dict]:
    records: list[dict] = []
    for op in operations:
        if op.op not in _INSTANCE_OPS or not op.id:
            continue
        instance_id = str(op.id)
        if op.type == EntityType.NODE:
            before_node = nodes_before.get(instance_id)
            after_node = nodes_after.get(instance_id)
            before_props = (
                None
                if op.op == MutationOperationType.CREATE
                else dict(before_node.properties) if before_node else None
            )
            after_props = (
                None
                if op.op == MutationOperationType.DELETE
                else dict(after_node.properties) if after_node else dict(op.set_properties or {})
            )
            label = op.label or (after_node.entity_type if after_node else before_node.entity_type if before_node else None)
            records.append(
                build_instance_change_record(
                    op=op.op.value,
                    entity_kind=EntityType.NODE.value,
                    instance_id=instance_id,
                    label=label,
                    before=before_props,
                    after=after_props,
                )
            )
            continue

        before_edge = edges_before.get(instance_id)
        after_edge = edges_after.get(instance_id)
        before_props = (
            None
            if op.op == MutationOperationType.CREATE
            else dict(before_edge.properties) if before_edge else None
        )
        after_props = (
            None
            if op.op == MutationOperationType.DELETE
            else dict(after_edge.properties) if after_edge else dict(op.set_properties or {})
        )
        label = op.label or (
            after_edge.relationship_type if after_edge else before_edge.relationship_type if before_edge else None
        )
        start_id = op.start_id or (after_edge.start_id if after_edge else before_edge.start_id if before_edge else None)
        end_id = op.end_id or (after_edge.end_id if after_edge else before_edge.end_id if before_edge else None)
        records.append(
            build_instance_change_record(
                op=op.op.value,
                entity_kind=EntityType.EDGE.value,
                instance_id=instance_id,
                label=label,
                before=before_props,
                after=after_props,
                start_id=start_id,
                end_id=end_id,
            )
        )
    return records


async def merge_instance_change_records(
    *,
    tenant_id: str,
    knowledge_graph_id: str,
    operations: list[MutationOperation],
    graph_reader: IWorkloadGraphReader,
    nodes_before: dict[str, WorkloadGraphNode] | None = None,
    edges_before: dict[str, WorkloadGraphRelationship] | None = None,
) -> list[dict]:
    """Build complete before/after records using snapshots captured around apply."""
    captured_nodes_before = nodes_before
    captured_edges_before = edges_before
    if captured_nodes_before is None or captured_edges_before is None:
        captured_nodes_before, captured_edges_before = await capture_before_snapshots(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            operations=operations,
            graph_reader=graph_reader,
        )
    nodes_after, edges_after = await capture_after_snapshots(
        tenant_id=tenant_id,
        knowledge_graph_id=knowledge_graph_id,
        operations=operations,
        graph_reader=graph_reader,
    )
    return build_instance_change_records(
        operations=operations,
        nodes_before=captured_nodes_before,
        edges_before=captured_edges_before,
        nodes_after=nodes_after,
        edges_after=edges_after,
    )


def _collect_ids(
    operations: list[MutationOperation],
    entity_type: EntityType,
    *,
    include_create: bool = True,
    include_delete: bool = True,
) -> tuple[str, ...]:
    ids: list[str] = []
    for op in operations:
        if op.type != entity_type or op.op not in _INSTANCE_OPS or not op.id:
            continue
        if op.op == MutationOperationType.CREATE and not include_create:
            continue
        if op.op == MutationOperationType.DELETE and not include_delete:
            continue
        ids.append(str(op.id))
    return tuple(dict.fromkeys(ids))
