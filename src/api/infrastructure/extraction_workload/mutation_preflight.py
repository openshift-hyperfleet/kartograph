"""Pre-apply validation for workload JSONL mutations (strict CREATE semantics)."""

from __future__ import annotations

from graph.domain.value_objects import EntityType, MutationOperation, MutationOperationType
from management.ports.exceptions import CanonicalSchemaMutationError

from extraction.ports.workload_graph import IWorkloadGraphReader
from infrastructure.extraction_workload.twin_edge_expansion import (
    expand_twin_edge_mutation_operations,
)
from management.domain.value_objects import OntologyConfig


def parse_mutation_jsonl(jsonl_content: str) -> list[MutationOperation]:
    from infrastructure.extraction_workload.graph_mutation_writer import (
        GraphWorkloadGraphMutationWriter,
    )

    return GraphWorkloadGraphMutationWriter.parse_jsonl(jsonl_content)


async def prepare_mutation_operations(
    *,
    jsonl_content: str,
    tenant_id: str,
    ontology: OntologyConfig | None,
) -> tuple[list[MutationOperation] | None, list[str]]:
    """Parse JSONL and expand bidirectional twin edge CREATE operations."""
    try:
        operations = parse_mutation_jsonl(jsonl_content)
    except CanonicalSchemaMutationError as exc:
        return None, [str(exc)]

    if ontology is not None:
        operations = expand_twin_edge_mutation_operations(
            operations,
            ontology=ontology,
            tenant_id=tenant_id,
        )
    return operations, []


async def validate_mutation_jsonl(
    *,
    jsonl_content: str,
    tenant_id: str,
    knowledge_graph_id: str,
    graph_reader: IWorkloadGraphReader | None,
    existing_type_keys: frozenset[tuple[str, str]],
    ontology: OntologyConfig | None = None,
) -> list[str]:
    """Return validation errors; empty list means the batch may be applied."""
    operations, errors = await prepare_mutation_operations(
        jsonl_content=jsonl_content,
        tenant_id=tenant_id,
        ontology=ontology,
    )
    if errors:
        return errors
    assert operations is not None

    errors: list[str] = []
    seen_create_ids: dict[str, int] = {}

    create_node_ids: list[str] = []
    create_edge_ids: list[str] = []
    update_node_ids: list[str] = []
    update_edge_ids: list[str] = []
    delete_node_ids: list[str] = []
    delete_edge_ids: list[str] = []
    slug_checks: dict[str, set[str]] = {}

    for line_num, operation in enumerate(operations, start=1):
        if operation.op == MutationOperationType.DELETE:
            if not operation.id:
                errors.append(f"Line {line_num}: DELETE requires id.")
            elif operation.type == EntityType.NODE.value:
                delete_node_ids.append(operation.id)
            elif operation.type == EntityType.EDGE.value:
                delete_edge_ids.append(operation.id)
            else:
                errors.append(f"Line {line_num}: DELETE type must be node or edge.")

        if operation.op == MutationOperationType.UPDATE:
            if not operation.id:
                errors.append(f"Line {line_num}: UPDATE requires id.")
            elif operation.type == EntityType.NODE.value:
                update_node_ids.append(operation.id)
            elif operation.type == EntityType.EDGE.value:
                update_edge_ids.append(operation.id)
            else:
                errors.append(f"Line {line_num}: UPDATE type must be node or edge.")

        if operation.op == MutationOperationType.DEFINE and operation.label:
            key = (operation.label, operation.type)
            if key in existing_type_keys:
                errors.append(
                    f"Line {line_num}: DEFINE for {operation.type} `{operation.label}` "
                    "already exists; update the ontology via kartograph_save_schema_ontology "
                    "instead of DEFINE."
                )

        if operation.op == MutationOperationType.CREATE and operation.id:
            if operation.id in seen_create_ids:
                errors.append(
                    f"Line {line_num}: duplicate CREATE id `{operation.id}` "
                    f"(first seen on line {seen_create_ids[operation.id]})."
                )
            else:
                seen_create_ids[operation.id] = line_num

            if operation.type == EntityType.NODE.value:
                create_node_ids.append(operation.id)
                slug = (operation.set_properties or {}).get("slug")
                label = operation.label
                if slug and label:
                    slug_checks.setdefault(label, set()).add(str(slug))
            elif operation.type == EntityType.EDGE.value:
                create_edge_ids.append(operation.id)

    if graph_reader is not None and not errors:
        if create_node_ids:
            existing_node_ids = await graph_reader.find_existing_node_ids(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                node_ids=tuple(create_node_ids),
            )
            for line_num, operation in enumerate(operations, start=1):
                if (
                    operation.op == MutationOperationType.CREATE
                    and operation.type == EntityType.NODE.value
                    and operation.id in existing_node_ids
                ):
                    errors.append(
                        f"Line {line_num}: node id `{operation.id}` already exists; "
                        "use UPDATE to change it."
                    )

        if create_edge_ids:
            existing_edge_ids = await graph_reader.find_existing_edge_ids(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                edge_ids=tuple(create_edge_ids),
            )
            for line_num, operation in enumerate(operations, start=1):
                if (
                    operation.op == MutationOperationType.CREATE
                    and operation.type == EntityType.EDGE.value
                    and operation.id in existing_edge_ids
                ):
                    errors.append(
                        f"Line {line_num}: edge id `{operation.id}` already exists; "
                        "use UPDATE to change it."
                    )

        for label, slugs in slug_checks.items():
            existing_slugs = await graph_reader.find_existing_slugs_for_entity_type(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                entity_type=label,
                slugs=tuple(slugs),
            )
            if not existing_slugs:
                continue
            for line_num, operation in enumerate(operations, start=1):
                if operation.op != MutationOperationType.CREATE:
                    continue
                if operation.type != EntityType.NODE.value or operation.label != label:
                    continue
                slug = str((operation.set_properties or {}).get("slug") or "")
                if slug in existing_slugs:
                    errors.append(
                        f"Line {line_num}: {label} slug `{slug}` already exists; "
                        "use UPDATE to change it."
                    )

        missing_node_ids = set(update_node_ids + delete_node_ids)
        if missing_node_ids:
            existing_node_ids = await graph_reader.find_existing_node_ids(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                node_ids=tuple(sorted(missing_node_ids)),
            )
            for line_num, operation in enumerate(operations, start=1):
                if operation.op not in {
                    MutationOperationType.UPDATE,
                    MutationOperationType.DELETE,
                }:
                    continue
                if operation.type != EntityType.NODE.value or not operation.id:
                    continue
                if operation.id not in existing_node_ids:
                    verb = operation.op.value
                    errors.append(
                        f"Line {line_num}: node id `{operation.id}` does not exist; "
                        f"cannot {verb}."
                    )

        missing_edge_ids = set(update_edge_ids + delete_edge_ids)
        if missing_edge_ids:
            existing_edge_ids = await graph_reader.find_existing_edge_ids(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                edge_ids=tuple(sorted(missing_edge_ids)),
            )
            for line_num, operation in enumerate(operations, start=1):
                if operation.op not in {
                    MutationOperationType.UPDATE,
                    MutationOperationType.DELETE,
                }:
                    continue
                if operation.type != EntityType.EDGE.value or not operation.id:
                    continue
                if operation.id not in existing_edge_ids:
                    verb = operation.op.value
                    errors.append(
                        f"Line {line_num}: edge id `{operation.id}` does not exist; "
                        f"cannot {verb}."
                    )

    return errors
