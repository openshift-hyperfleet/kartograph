"""AGE bulk loading strategy using PostgreSQL COPY protocol.

This strategy optimizes bulk loading for Apache AGE by:
1. Using PostgreSQL COPY to rapidly load data into staging tables
2. Using direct SQL INSERT/UPDATE to write to AGE tables (bypassing slow Cypher MERGE)
3. Computing graphids via AGE's _graphid function and sequences

This approach is ~100x faster than Cypher MERGE for large batches.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
    MutationResult,
)
from graph.infrastructure.observability import DefaultAgeBulkLoadingProbe
from graph.ports.age_bulk_loading_probe import AgeBulkLoadingProbe
from graph.ports.bulk_loading import BulkLoadingStrategy
from graph.ports.observability import MutationProbe
from graph.ports.protocols import GraphClientProtocol, TransactionalIndexingProtocol

from .indexing import AgeIndexingStrategy
from .queries import AgeQueryBuilder
from .staging import StagingTableManager
from .utils import validate_label_name


class AgeBulkLoadingStrategy(BulkLoadingStrategy):
    """AGE-specific bulk loading strategy using direct SQL INSERT.

    This strategy bypasses Cypher MERGE and writes directly to AGE's
    internal PostgreSQL tables for maximum performance.

    Uses advisory locks to ensure concurrency safety.
    """

    DEFAULT_BATCH_SIZE = 1000

    def __init__(
        self,
        indexing_strategy: TransactionalIndexingProtocol | None = None,
        batch_size: int | None = None,
        bulk_loading_probe: AgeBulkLoadingProbe | None = None,
    ):
        self._indexing_strategy = indexing_strategy or AgeIndexingStrategy()
        self._batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self._bulk_probe = bulk_loading_probe or DefaultAgeBulkLoadingProbe()
        self._staging = StagingTableManager()
        self._queries = AgeQueryBuilder

    def apply_batch(
        self,
        client: GraphClientProtocol,
        operations: list[MutationOperation],
        probe: MutationProbe,
        graph_name: str,
    ) -> MutationResult:
        """Apply mutations using direct SQL INSERT/UPDATE."""
        start_time = time.perf_counter()
        session_id = uuid.uuid4().hex[:16]

        try:
            # Partition operations by type
            create_nodes = [
                op
                for op in operations
                if op.op == MutationOperationType.CREATE and op.type == EntityType.NODE
            ]
            create_edges = [
                op
                for op in operations
                if op.op == MutationOperationType.CREATE and op.type == EntityType.EDGE
            ]
            delete_edges = [
                op
                for op in operations
                if op.op == MutationOperationType.DELETE and op.type == EntityType.EDGE
            ]
            delete_nodes = [
                op
                for op in operations
                if op.op == MutationOperationType.DELETE and op.type == EntityType.NODE
            ]
            update_ops = [
                op for op in operations if op.op == MutationOperationType.UPDATE
            ]

            conn = client.raw_connection
            total_batches = 0

            with conn.cursor() as cursor:
                # Acquire advisory locks for all labels we'll modify
                all_labels = {op.label for op in create_nodes if op.label} | {
                    op.label for op in create_edges if op.label
                }
                for label in all_labels:
                    self._queries.acquire_advisory_lock(cursor, graph_name, label)

                # Execute DELETEs first (edges before nodes for referential integrity)
                if delete_edges:
                    total_batches += self._execute_deletes(
                        cursor, delete_edges, EntityType.EDGE, probe, graph_name
                    )
                if delete_nodes:
                    total_batches += self._execute_deletes(
                        cursor, delete_nodes, EntityType.NODE, probe, graph_name
                    )

                # Execute CREATEs (nodes before edges for referential integrity)
                if create_nodes:
                    total_batches += self._execute_creates(
                        cursor,
                        create_nodes,
                        EntityType.NODE,
                        graph_name,
                        session_id,
                        probe,
                    )
                if create_edges:
                    total_batches += self._execute_creates(
                        cursor,
                        create_edges,
                        EntityType.EDGE,
                        graph_name,
                        session_id,
                        probe,
                    )

                # Execute UPDATEs
                if update_ops:
                    total_batches += self._execute_updates(
                        cursor, update_ops, graph_name, probe
                    )

                conn.commit()

            duration_ms = (time.perf_counter() - start_time) * 1000
            probe.apply_batch_completed(
                total_operations=len(operations),
                total_batches=total_batches,
                duration_ms=duration_ms,
                success=True,
            )

            return MutationResult(success=True, operations_applied=len(operations))

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            probe.apply_batch_completed(
                total_operations=len(operations),
                total_batches=0,
                duration_ms=duration_ms,
                success=False,
            )
            try:
                client.raw_connection.rollback()
            except Exception:
                pass
            return MutationResult(success=False, operations_applied=0, errors=[str(e)])

    def _pre_create_labels_and_indexes(
        self,
        cursor: Any,
        graph_name: str,
        labels: list[str],
        entity_type: EntityType,
    ) -> set[str]:
        """Pre-create all new labels and their indexes in batch."""
        existing_labels = self._queries.get_existing_labels(cursor, graph_name)
        new_labels = set(labels) - existing_labels

        for label in new_labels:
            self._queries.create_label(cursor, graph_name, label, entity_type)

        for label in new_labels:
            self._indexing_strategy.create_label_indexes(
                cursor, graph_name, label, entity_type
            )

        return new_labels

    def _execute_creates(
        self,
        cursor: Any,
        operations: list[MutationOperation],
        entity_type: EntityType,
        graph_name: str,
        session_id: str,
        probe: MutationProbe,
    ) -> int:
        """Execute CREATE operations using staging tables."""
        entity_name = entity_type.value

        # Validate all label names
        for op in operations:
            if op.label:
                validate_label_name(op.label)

        # Create and populate staging table
        if entity_type == EntityType.NODE:
            table_name = self._staging.create_node_staging_table(cursor, session_id)
        else:
            table_name = self._staging.create_edge_staging_table(cursor, session_id)
        self._bulk_probe.staging_table_created(table_name, entity_name)

        copy_start = time.perf_counter()
        if entity_type == EntityType.NODE:
            row_count = self._staging.copy_nodes_to_staging(
                cursor, table_name, operations, graph_name
            )
        else:
            row_count = self._staging.copy_edges_to_staging(
                cursor, table_name, operations, graph_name
            )
        self._bulk_probe.staging_data_copied(
            table_name,
            entity_name,
            row_count,
            (time.perf_counter() - copy_start) * 1000,
        )

        # Create staging table indexes
        index_start = time.perf_counter()
        self._staging.create_label_index(cursor, table_name)
        self._bulk_probe.staging_index_created(
            table_name, "label", (time.perf_counter() - index_start) * 1000
        )

        # Edge-specific: create resolution indexes and resolve graphids
        if entity_type == EntityType.EDGE:
            index_start = time.perf_counter()
            self._staging.create_edge_resolution_indexes(cursor, table_name)
            self._bulk_probe.staging_index_created(
                table_name,
                "start_id/end_id",
                (time.perf_counter() - index_start) * 1000,
            )

            lookup_start = time.perf_counter()
            lookup_table, lookup_row_count = self._staging.create_graphid_lookup_table(
                cursor, graph_name, session_id
            )
            self._bulk_probe.graphid_lookup_table_created(
                lookup_row_count, (time.perf_counter() - lookup_start) * 1000
            )

            resolve_start = time.perf_counter()
            self._staging.resolve_edge_graphids(cursor, table_name, lookup_table)
            resolve_duration = (time.perf_counter() - resolve_start) * 1000

            resolved_count = self._queries.count_resolved_edges(cursor, table_name)
            self._bulk_probe.graphids_resolved(
                row_count, resolved_count, resolve_duration
            )

            # Check for orphaned edges
            validation_start = time.perf_counter()
            self._staging.check_for_orphaned_edges(cursor, table_name, probe)
            self._bulk_probe.validation_completed(
                "orphaned_edges",
                entity_name,
                (time.perf_counter() - validation_start) * 1000,
            )

        # Check for duplicates
        validation_start = time.perf_counter()
        self._staging.check_for_duplicate_ids(cursor, table_name, entity_name, probe)
        self._bulk_probe.validation_completed(
            "duplicate_ids",
            entity_name,
            (time.perf_counter() - validation_start) * 1000,
        )

        # Get distinct labels and pre-create
        validation_start = time.perf_counter()
        labels = self._staging.fetch_distinct_labels(cursor, table_name)
        self._bulk_probe.validation_completed(
            "distinct_labels",
            entity_name,
            (time.perf_counter() - validation_start) * 1000,
        )

        labels_start = time.perf_counter()
        new_labels = self._pre_create_labels_and_indexes(
            cursor, graph_name, labels, entity_type
        )
        self._bulk_probe.labels_pre_created(
            entity_name,
            len(labels),
            len(new_labels),
            (time.perf_counter() - labels_start) * 1000,
        )

        # Process each label
        batches = 0
        for label in labels:
            batch_start = time.perf_counter()

            label_info = self._queries.get_label_info(cursor, graph_name, label)
            if label_info is None:
                raise ValueError(f"Label '{label}' not found in graph '{graph_name}'")

            label_id, seq_name = label_info
            updated, inserted = self._queries.execute_label_upsert(
                cursor=cursor,
                graph_name=graph_name,
                label=label,
                label_id=label_id,
                seq_name=seq_name,
                staging_table=table_name,
                entity_type=entity_type,
                is_new_label=label in new_labels,
            )

            probe.batch_applied(
                operation=MutationOperationType.CREATE,
                entity_type=entity_name,
                label=label,
                count=updated + inserted,
                duration_ms=(time.perf_counter() - batch_start) * 1000,
            )
            batches += 1

        return batches

    def _execute_deletes(
        self,
        cursor: Any,
        operations: list[MutationOperation],
        entity_type: EntityType,
        probe: MutationProbe,
        graph_name: str,
    ) -> int:
        """Execute DELETE operations in batches."""
        batches = 0
        for i in range(0, len(operations), self._batch_size):
            batch = operations[i : i + self._batch_size]
            batch_start = time.perf_counter()

            ids = [op.id for op in batch if op.id is not None]

            if len(ids) != len(batch):
                raise ValueError(
                    "Detected malformed DELETE operation. At least one operation missing an ID."
                )

            if entity_type == EntityType.NODE:
                deleted = self._queries.delete_nodes_with_detach(
                    cursor, graph_name, ids
                )
            else:
                deleted = self._queries.delete_edges(cursor, graph_name, ids)

            probe.batch_applied(
                operation=MutationOperationType.DELETE,
                entity_type=str(entity_type),
                label=None,
                count=deleted,
                duration_ms=(time.perf_counter() - batch_start) * 1000,
            )
            batches += 1

        return batches

    def _execute_updates(
        self,
        cursor: Any,
        operations: list[MutationOperation],
        graph_name: str,
        probe: MutationProbe,
    ) -> int:
        """Execute UPDATE operations."""
        batches = 0

        for op in operations:
            if op.id is None:
                raise RuntimeError("Malformed UPDATE operation, missing ID.")

            batch_start = time.perf_counter()

            table_name = self._queries.find_entity_table(
                cursor, graph_name, op.id, op.type
            )
            if not table_name:
                continue

            if op.set_properties:
                self._queries.update_properties(
                    cursor, table_name, op.id, op.set_properties
                )

            if op.remove_properties:
                self._queries.remove_properties(
                    cursor, table_name, op.id, list(op.remove_properties)
                )

            probe.batch_applied(
                operation=MutationOperationType.UPDATE,
                entity_type=str(op.type),
                label=None,
                count=1,
                duration_ms=(time.perf_counter() - batch_start) * 1000,
            )
            batches += 1

        return batches
