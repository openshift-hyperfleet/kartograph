"""Unit tests for MutationApplier._sort_operations.

Spec requirement: Referential Integrity Ordering.
GIVEN a batch with mixed operation types
WHEN the mutations are applied
THEN DEFINE operations run first
AND DELETE operations run next (edges before nodes)
AND CREATE operations follow (nodes before edges)
AND UPDATE operations run last
"""

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)


def _make_op(
    op: MutationOperationType,
    entity_type: EntityType,
    entity_id: str | None = None,
    label: str | None = None,
) -> MutationOperation:
    """Helper: build a minimal MutationOperation for sort testing."""
    kwargs: dict = {"op": op, "type": entity_type}
    if entity_id is not None:
        kwargs["id"] = entity_id
    if op == MutationOperationType.DEFINE:
        kwargs["label"] = label or "thing"
        kwargs["description"] = "A thing"
        kwargs["required_properties"] = set()
    elif op == MutationOperationType.CREATE:
        kwargs["label"] = label or "thing"
        kwargs["set_properties"] = {
            "data_source_id": "ds-1",
            "source_path": "x.md",
            "slug": "x",
            "knowledge_graph_id": "kg-1",
        }
    elif op == MutationOperationType.UPDATE:
        kwargs["set_properties"] = {"name": "updated"}
    # DELETE needs only op, type, id
    return MutationOperation(**kwargs)


class TestSortOperationsReferentialIntegrity:
    """Tests that _sort_operations produces spec-mandated execution order."""

    def test_sort_order_define_delete_create_update(self):
        """Mixed operations must be sorted: DEFINE → DELETE(edge/node) → CREATE(node/edge) → UPDATE.

        Spec: Referential Integrity Ordering scenario.
        """
        from unittest.mock import MagicMock

        from graph.infrastructure.mutation_applier import MutationApplier

        # Create a MutationApplier with mock dependencies (we only call _sort_operations)
        applier = MutationApplier(
            client=MagicMock(),
            bulk_loading_strategy=MagicMock(),
        )

        # Build a maximally-mixed list: one of each relevant sub-type in arbitrary order
        update_op = _make_op(
            MutationOperationType.UPDATE,
            EntityType.NODE,
            entity_id="thing:aaaaaaaaaaaaaaaa",
        )
        create_edge_op = _make_op(
            MutationOperationType.CREATE,
            EntityType.EDGE,
            entity_id="rel:bbbbbbbbbbbbbbbb",
            label="relates_to",
        )
        delete_node_op = _make_op(
            MutationOperationType.DELETE,
            EntityType.NODE,
            entity_id="thing:cccccccccccccccc",
        )
        define_op = _make_op(
            MutationOperationType.DEFINE,
            EntityType.NODE,
            label="thing",
        )
        delete_edge_op = _make_op(
            MutationOperationType.DELETE,
            EntityType.EDGE,
            entity_id="rel:dddddddddddddddd",
        )
        create_node_op = _make_op(
            MutationOperationType.CREATE,
            EntityType.NODE,
            entity_id="thing:eeeeeeeeeeeeeeee",
            label="thing",
        )

        # Submit in a deliberately wrong order
        mixed = [
            update_op,
            create_edge_op,
            delete_node_op,
            define_op,
            delete_edge_op,
            create_node_op,
        ]

        sorted_ops = applier._sort_operations(mixed)

        # --- Assert spec-mandated order ---
        ops_sequence = [(op.op, op.type) for op in sorted_ops]

        # Position 0: DEFINE (any entity type)
        assert sorted_ops[0].op == MutationOperationType.DEFINE, (
            f"First op must be DEFINE, got {sorted_ops[0].op}"
        )

        # Position 1: DELETE edge (edges before nodes)
        assert sorted_ops[1].op == MutationOperationType.DELETE, (
            f"Second op must be DELETE, got {sorted_ops[1].op}"
        )
        assert sorted_ops[1].type == EntityType.EDGE, (
            f"First DELETE must be an EDGE delete, got {sorted_ops[1].type}"
        )

        # Position 2: DELETE node
        assert sorted_ops[2].op == MutationOperationType.DELETE, (
            f"Third op must be DELETE, got {sorted_ops[2].op}"
        )
        assert sorted_ops[2].type == EntityType.NODE, (
            f"Second DELETE must be a NODE delete, got {sorted_ops[2].type}"
        )

        # Position 3: CREATE node (nodes before edges)
        assert sorted_ops[3].op == MutationOperationType.CREATE, (
            f"Fourth op must be CREATE, got {sorted_ops[3].op}"
        )
        assert sorted_ops[3].type == EntityType.NODE, (
            f"First CREATE must be a NODE create, got {sorted_ops[3].type}"
        )

        # Position 4: CREATE edge
        assert sorted_ops[4].op == MutationOperationType.CREATE, (
            f"Fifth op must be CREATE, got {sorted_ops[4].op}"
        )
        assert sorted_ops[4].type == EntityType.EDGE, (
            f"Second CREATE must be an EDGE create, got {sorted_ops[4].type}"
        )

        # Position 5: UPDATE (last)
        assert sorted_ops[5].op == MutationOperationType.UPDATE, (
            f"Last op must be UPDATE, got {sorted_ops[5].op}"
        )

        # Sanity: all six input ops are present in output
        assert len(sorted_ops) == 6, (
            f"Expected 6 sorted ops, got {len(sorted_ops)}: {ops_sequence}"
        )

    def test_sort_preserves_all_operations(self):
        """_sort_operations must not drop or duplicate any operation."""
        from unittest.mock import MagicMock

        from graph.infrastructure.mutation_applier import MutationApplier

        applier = MutationApplier(
            client=MagicMock(),
            bulk_loading_strategy=MagicMock(),
        )

        ops = [
            _make_op(
                MutationOperationType.DELETE, EntityType.NODE, "thing:1111111111111111"
            ),
            _make_op(MutationOperationType.DEFINE, EntityType.NODE, label="thing"),
            _make_op(
                MutationOperationType.CREATE,
                EntityType.NODE,
                "thing:2222222222222222",
                label="thing",
            ),
        ]

        sorted_ops = applier._sort_operations(ops)

        assert len(sorted_ops) == len(ops)
        # All original ops are represented (identity check via id attribute)
        original_ids = {id(op) for op in ops}
        sorted_ids = {id(op) for op in sorted_ops}
        assert original_ids == sorted_ids

    def test_sort_homogeneous_list_unchanged_length(self):
        """Sorting a list of only one op type returns all ops unchanged in length."""
        from unittest.mock import MagicMock

        from graph.infrastructure.mutation_applier import MutationApplier

        applier = MutationApplier(
            client=MagicMock(),
            bulk_loading_strategy=MagicMock(),
        )

        delete_ops = [
            _make_op(MutationOperationType.DELETE, EntityType.NODE, f"thing:{i:016x}")
            for i in range(5)
        ]

        sorted_ops = applier._sort_operations(delete_ops)

        assert len(sorted_ops) == 5
        assert all(op.op == MutationOperationType.DELETE for op in sorted_ops)
