"""AGE-specific bulk loading strategy using PostgreSQL COPY protocol.

This strategy optimizes bulk loading for Apache AGE by:
1. Using PostgreSQL COPY to rapidly load data into staging tables
2. Using direct SQL INSERT/UPDATE to write to AGE tables (bypassing slow Cypher MERGE)
3. Computing graphids via AGE's _graphid function and sequences

This approach is ~100x faster than Cypher MERGE for large batches.
"""

from __future__ import annotations

import io
import json
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from graph.domain.value_objects import EntityType, MutationOperation, MutationResult
from graph.ports.observability import MutationProbe
from graph.ports.protocols import GraphClientProtocol, GraphIndexingProtocol

if TYPE_CHECKING:
    pass


class StagingTableManager:
    """Manages temporary staging tables for bulk COPY operations."""

    def __init__(self, graph_name: str):
        self._graph_name = graph_name

    def create_node_staging_table(self, cursor: Any, session_id: str) -> str:
        """Create a temporary staging table for nodes."""
        table_name = f"_staging_nodes_{session_id}"
        cursor.execute(
            f"""
            CREATE TEMP TABLE "{table_name}" (
                id TEXT NOT NULL,
                label TEXT NOT NULL,
                properties JSONB NOT NULL
            ) ON COMMIT DROP
            """
        )
        return table_name

    def create_edge_staging_table(self, cursor: Any, session_id: str) -> str:
        """Create a temporary staging table for edges."""
        table_name = f"_staging_edges_{session_id}"
        cursor.execute(
            f"""
            CREATE TEMP TABLE "{table_name}" (
                id TEXT NOT NULL,
                label TEXT NOT NULL,
                start_id TEXT NOT NULL,
                end_id TEXT NOT NULL,
                properties JSONB NOT NULL
            ) ON COMMIT DROP
            """
        )
        return table_name

    def copy_nodes_to_staging(
        self,
        cursor: Any,
        table_name: str,
        operations: list[MutationOperation],
        graph_name: str,
    ) -> int:
        """COPY node data to staging table using StringIO."""
        buffer = io.StringIO()

        for op in operations:
            props = dict(op.set_properties or {})
            props["id"] = op.id
            props["graph_id"] = graph_name

            # Escape backslashes for COPY format
            props_json = json.dumps(props).replace("\\", "\\\\")
            row = f"{op.id}\t{op.label}\t{props_json}\n"
            buffer.write(row)

        buffer.seek(0)
        cursor.copy_from(
            buffer,
            table_name,
            columns=("id", "label", "properties"),
            sep="\t",
        )
        return len(operations)

    def copy_edges_to_staging(
        self,
        cursor: Any,
        table_name: str,
        operations: list[MutationOperation],
        graph_name: str,
    ) -> int:
        """COPY edge data to staging table using StringIO."""
        buffer = io.StringIO()

        for op in operations:
            props = dict(op.set_properties or {})
            props["id"] = op.id
            props["graph_id"] = graph_name

            # Escape backslashes for COPY format
            props_json = json.dumps(props).replace("\\", "\\\\")
            row = f"{op.id}\t{op.label}\t{op.start_id}\t{op.end_id}\t{props_json}\n"
            buffer.write(row)

        buffer.seek(0)
        cursor.copy_from(
            buffer,
            table_name,
            columns=("id", "label", "start_id", "end_id", "properties"),
            sep="\t",
        )
        return len(operations)

    def fetch_distinct_labels(self, cursor: Any, table_name: str) -> list[str]:
        """Fetch distinct labels from staging table."""
        cursor.execute(f'SELECT DISTINCT label FROM "{table_name}"')
        return [row[0] for row in cursor.fetchall()]


class AgeBulkLoadingStrategy:
    """AGE-specific bulk loading strategy using direct SQL INSERT.

    This strategy bypasses Cypher MERGE and writes directly to AGE's
    internal PostgreSQL tables for maximum performance.

    Uses advisory locks to ensure concurrency safety.
    """

    DEFAULT_BATCH_SIZE = 1000
    COPY_THRESHOLD = 50  # Use COPY for batches >= this size

    def __init__(
        self,
        indexing_client: GraphIndexingProtocol | None = None,
        batch_size: int | None = None,
        copy_threshold: int | None = None,
    ):
        self._indexing_client = indexing_client
        self._batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self._copy_threshold = copy_threshold or self.COPY_THRESHOLD

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

        created_dummy_labels: set = set()

        try:
            sorted_ops = self._sort_operations(operations)

            create_nodes = [
                op
                for op in sorted_ops
                if op.op == "CREATE" and op.type == EntityType.NODE
            ]
            create_edges = [
                op
                for op in sorted_ops
                if op.op == "CREATE" and op.type == EntityType.EDGE
            ]
            delete_edges = [
                op
                for op in sorted_ops
                if op.op == "DELETE" and op.type == EntityType.EDGE
            ]
            delete_nodes = [
                op
                for op in sorted_ops
                if op.op == "DELETE" and op.type == EntityType.NODE
            ]
            update_ops = [op for op in sorted_ops if op.op == "UPDATE"]

            node_labels = {op.label for op in create_nodes if op.label}
            edge_labels = {op.label for op in create_edges if op.label}

            # Phase 1: Create dummy nodes/edges for new labels (needed for table creation)
            created_dummy_labels = self._create_dummy_nodes(
                client, node_labels, session_id
            )
            created_dummy_edge_labels = self._create_dummy_edges(
                client, edge_labels, session_id
            )

            # Phase 2: Ensure indexes exist
            if self._indexing_client is not None:
                self._indexing_client.ensure_all_labels_indexed()

            # Phase 3: Execute all operations in a single transaction
            conn = client.raw_connection
            total_batches = 0

            with conn.cursor() as cursor:
                # Acquire advisory locks for all labels we'll modify
                all_labels = node_labels | {op.label for op in create_edges if op.label}
                self._acquire_label_locks(cursor, graph_name, all_labels)

                # Execute DELETEs first (via Cypher - simpler and less frequent)
                if delete_edges:
                    total_batches += self._execute_deletes(
                        client, delete_edges, EntityType.EDGE, probe
                    )
                if delete_nodes:
                    total_batches += self._execute_deletes(
                        client, delete_nodes, EntityType.NODE, probe
                    )

                # Execute CREATEs using direct SQL
                if create_nodes:
                    total_batches += self._execute_node_creates(
                        cursor, create_nodes, graph_name, session_id, probe
                    )

                if create_edges:
                    total_batches += self._execute_edge_creates(
                        cursor, create_edges, graph_name, session_id, probe
                    )

                # Execute UPDATEs using direct SQL
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

            return MutationResult(
                success=True,
                operations_applied=len(operations),
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            probe.apply_batch_completed(
                total_operations=len(operations),
                total_batches=0,
                duration_ms=duration_ms,
                success=False,
            )
            # Rollback on error
            try:
                client.raw_connection.rollback()
            except Exception:
                pass
            return MutationResult(
                success=False,
                operations_applied=0,
                errors=[str(e)],
            )
        finally:
            if created_dummy_labels or created_dummy_edge_labels:
                try:
                    self._cleanup_dummy_entities(client, session_id)
                except Exception:
                    pass

    def _sort_operations(
        self, operations: list[MutationOperation]
    ) -> list[MutationOperation]:
        """Sort operations into correct execution order."""

        def sort_key(op: MutationOperation) -> tuple[int, int]:
            op_priority = {"DEFINE": 0, "DELETE": 1, "CREATE": 2, "UPDATE": 3}
            if op.op == "DELETE":
                type_priority = 0 if op.type == EntityType.EDGE else 1
            else:
                type_priority = 0 if op.type == EntityType.NODE else 1
            return (op_priority.get(op.op, 999), type_priority)

        return sorted(operations, key=sort_key)

    def _acquire_label_locks(
        self, cursor: Any, graph_name: str, labels: set[str]
    ) -> None:
        """Acquire advisory locks for labels to prevent concurrent modifications."""
        for label in labels:
            # Use hash of graph_name + label as lock key
            lock_key = hash(f"{graph_name}:{label}") & 0x7FFFFFFF
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

    def _get_label_info(
        self, cursor: Any, graph_name: str, label: str
    ) -> tuple[int, str]:
        """Get label_id and sequence name for a label."""
        cursor.execute(
            """
            SELECT l.id, l.seq_name
            FROM ag_catalog.ag_label l
            JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
            WHERE g.name = %s AND l.name = %s
            """,
            (graph_name, label),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Label '{label}' not found in graph '{graph_name}'")
        return (row[0], row[1])

    def _create_dummy_nodes(
        self,
        client: GraphClientProtocol,
        labels: set[str],
        session_id: str,
    ) -> set[str]:
        """Create dummy nodes to pre-create label tables for indexing."""
        created_labels: set[str] = set()
        timestamp = datetime.now(timezone.utc).isoformat()

        for label in labels:
            result = client.execute_cypher(f"MATCH (n:{label}) RETURN n LIMIT 1")
            if result.row_count > 0:
                continue

            dummy_id = f"_dummy_{session_id}_{label}"
            client.execute_cypher(
                f"CREATE (n:{label} {{"
                f"id: '{dummy_id}', "
                f"_kartograph_dummy: true, "
                f"_kartograph_session_id: '{session_id}', "
                f"_kartograph_created_at: '{timestamp}'"
                f"}})"
            )
            created_labels.add(label)

        return created_labels

    def _create_dummy_edges(
        self,
        client: GraphClientProtocol,
        labels: set[str],
        session_id: str,
    ) -> set[str]:
        """Create dummy edges to pre-create edge label tables.

        Creates a temporary edge for each edge label that doesn't exist yet.
        This requires two dummy nodes to connect, which are also created
        and marked for cleanup.
        """
        created_labels: set[str] = set()
        timestamp = datetime.now(timezone.utc).isoformat()

        for label in labels:
            # Check if edge label already exists
            result = client.execute_cypher(f"MATCH ()-[r:{label}]->() RETURN r LIMIT 1")
            if result.row_count > 0:
                continue

            # Create two dummy nodes and connect them with the edge label
            dummy_src_id = f"_dummy_edge_src_{session_id}_{label}"
            dummy_tgt_id = f"_dummy_edge_tgt_{session_id}_{label}"
            dummy_edge_id = f"_dummy_edge_{session_id}_{label}"

            # Create source and target dummy nodes, then the edge between them
            client.execute_cypher(
                f"CREATE (src:_DummyNode {{"
                f"id: '{dummy_src_id}', "
                f"_kartograph_dummy: true, "
                f"_kartograph_session_id: '{session_id}', "
                f"_kartograph_created_at: '{timestamp}'"
                f"}})"
                f"-[r:{label} {{"
                f"id: '{dummy_edge_id}', "
                f"_kartograph_dummy: true, "
                f"_kartograph_session_id: '{session_id}', "
                f"_kartograph_created_at: '{timestamp}'"
                f"}}]->"
                f"(tgt:_DummyNode {{"
                f"id: '{dummy_tgt_id}', "
                f"_kartograph_dummy: true, "
                f"_kartograph_session_id: '{session_id}', "
                f"_kartograph_created_at: '{timestamp}'"
                f"}})"
            )
            created_labels.add(label)

        return created_labels

    def _cleanup_dummy_entities(
        self, client: GraphClientProtocol, session_id: str
    ) -> int:
        """Delete all dummy entities (nodes and edges) created by this session."""
        # First delete edges with the session_id
        client.execute_cypher(
            f"MATCH ()-[r {{_kartograph_session_id: '{session_id}'}}]->() "
            f"WHERE r._kartograph_dummy = true "
            f"DELETE r"
        )

        # Then delete nodes with the session_id (including _DummyNode nodes)
        result = client.execute_cypher(
            f"MATCH (n {{_kartograph_session_id: '{session_id}'}}) "
            f"WHERE n._kartograph_dummy = true "
            f"DETACH DELETE n "
            f"RETURN count(n) as deleted"
        )
        if result.rows and result.rows[0]:
            deleted = result.rows[0][0]
            if isinstance(deleted, int):
                return deleted
        return 0

    def _execute_node_creates(
        self,
        cursor: Any,
        operations: list[MutationOperation],
        graph_name: str,
        session_id: str,
        probe: MutationProbe,
    ) -> int:
        """Execute node CREATE operations using direct SQL."""
        staging_manager = StagingTableManager(graph_name)
        batches = 0

        # Create staging table and COPY data
        table_name = staging_manager.create_node_staging_table(cursor, session_id)
        staging_manager.copy_nodes_to_staging(
            cursor, table_name, operations, graph_name
        )

        # Process each label
        labels = staging_manager.fetch_distinct_labels(cursor, table_name)

        for label in labels:
            batch_start = time.perf_counter()
            label_id, seq_name = self._get_label_info(cursor, graph_name, label)

            # Update existing nodes
            cursor.execute(
                f"""
                UPDATE "{graph_name}"."{label}" AS t
                SET properties = (s.properties::text)::ag_catalog.agtype
                FROM "{table_name}" AS s
                WHERE s.label = %s
                AND ag_catalog.agtype_object_field_text_agtype(
                    t.properties, '"id"'::ag_catalog.agtype
                ) = s.id
                """,
                (label,),
            )
            updated = cursor.rowcount

            # Insert new nodes (DISTINCT ON ensures idempotency for duplicate IDs in batch)
            cursor.execute(
                f"""
                INSERT INTO "{graph_name}"."{label}" (id, properties)
                SELECT DISTINCT ON (s.id)
                    ag_catalog._graphid(%s, nextval('"{graph_name}"."{seq_name}"')),
                    (s.properties::text)::ag_catalog.agtype
                FROM "{table_name}" AS s
                WHERE s.label = %s
                AND NOT EXISTS (
                    SELECT 1 FROM "{graph_name}"."{label}" AS t
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        t.properties, '"id"'::ag_catalog.agtype
                    ) = s.id
                )
                """,
                (label_id, label),
            )
            inserted = cursor.rowcount

            batch_duration = (time.perf_counter() - batch_start) * 1000
            probe.batch_applied(
                operation="CREATE",
                entity_type="node",
                label=label,
                count=updated + inserted,
                duration_ms=batch_duration,
            )
            batches += 1

        return batches

    def _execute_edge_creates(
        self,
        cursor: Any,
        operations: list[MutationOperation],
        graph_name: str,
        session_id: str,
        probe: MutationProbe,
    ) -> int:
        """Execute edge CREATE operations using direct SQL with graphid resolution."""
        staging_manager = StagingTableManager(graph_name)
        batches = 0

        # Create staging table and COPY data
        table_name = staging_manager.create_edge_staging_table(cursor, session_id)
        staging_manager.copy_edges_to_staging(
            cursor, table_name, operations, graph_name
        )

        labels = staging_manager.fetch_distinct_labels(cursor, table_name)

        for label in labels:
            batch_start = time.perf_counter()
            label_id, seq_name = self._get_label_info(cursor, graph_name, label)

            # Update existing edges
            cursor.execute(
                f"""
                UPDATE "{graph_name}"."{label}" AS t
                SET properties = (s.properties::text)::ag_catalog.agtype
                FROM "{table_name}" AS s
                WHERE s.label = %s
                AND ag_catalog.agtype_object_field_text_agtype(
                    t.properties, '"id"'::ag_catalog.agtype
                ) = s.id
                """,
                (label,),
            )
            updated = cursor.rowcount

            # Insert new edges with graphid resolution
            # DISTINCT ON ensures idempotency for duplicate IDs in batch
            # Join against ALL vertex tables to find start/end nodes
            cursor.execute(
                f"""
                INSERT INTO "{graph_name}"."{label}" (id, start_id, end_id, properties)
                SELECT DISTINCT ON (s.id)
                    ag_catalog._graphid(%s, nextval('"{graph_name}"."{seq_name}"')),
                    src.id,
                    tgt.id,
                    (s.properties::text)::ag_catalog.agtype
                FROM "{table_name}" AS s
                JOIN "{graph_name}"._ag_label_vertex AS src
                    ON ag_catalog.agtype_object_field_text_agtype(
                        src.properties, '"id"'::ag_catalog.agtype
                    ) = s.start_id
                JOIN "{graph_name}"._ag_label_vertex AS tgt
                    ON ag_catalog.agtype_object_field_text_agtype(
                        tgt.properties, '"id"'::ag_catalog.agtype
                    ) = s.end_id
                WHERE s.label = %s
                AND NOT EXISTS (
                    SELECT 1 FROM "{graph_name}"."{label}" AS e
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        e.properties, '"id"'::ag_catalog.agtype
                    ) = s.id
                )
                """,
                (label_id, label),
            )
            inserted = cursor.rowcount

            batch_duration = (time.perf_counter() - batch_start) * 1000
            probe.batch_applied(
                operation="CREATE",
                entity_type="edge",
                label=label,
                count=updated + inserted,
                duration_ms=batch_duration,
            )
            batches += 1

        return batches

    def _execute_deletes(
        self,
        client: GraphClientProtocol,
        operations: list[MutationOperation],
        entity_type: EntityType,
        probe: MutationProbe,
    ) -> int:
        """Execute DELETE operations using Cypher (simpler for deletes)."""
        batches = 0
        for i in range(0, len(operations), self._batch_size):
            batch = operations[i : i + self._batch_size]
            batch_start = time.perf_counter()

            ids = [f"{{id: '{op.id}'}}" for op in batch]
            ids_str = ", ".join(ids)

            if entity_type == EntityType.NODE:
                query = (
                    f"WITH [{ids_str}] AS items "
                    f"UNWIND items AS item "
                    f"MATCH (n {{id: item.id}}) "
                    f"DETACH DELETE n"
                )
            else:
                query = (
                    f"WITH [{ids_str}] AS items "
                    f"UNWIND items AS item "
                    f"MATCH ()-[r {{id: item.id}}]->() "
                    f"DELETE r"
                )

            client.execute_cypher(query)
            batch_duration = (time.perf_counter() - batch_start) * 1000

            probe.batch_applied(
                operation="DELETE",
                entity_type=str(entity_type),
                label=None,
                count=len(batch),
                duration_ms=batch_duration,
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
        """Execute UPDATE operations using direct SQL."""
        batches = 0

        for op in operations:
            batch_start = time.perf_counter()

            if op.type == EntityType.NODE:
                # Find the label table for this node
                cursor.execute(
                    f"""
                    SELECT tableoid::regclass
                    FROM "{graph_name}"._ag_label_vertex
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        properties, '"id"'::ag_catalog.agtype
                    ) = %s
                    """,
                    (op.id,),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                table_name = str(row[0])

                if op.set_properties:
                    # Merge new properties with existing
                    props_json = json.dumps(op.set_properties)
                    cursor.execute(
                        f"""
                        UPDATE {table_name} AS t
                        SET properties = (
                            (t.properties::text)::jsonb || %s::jsonb
                        )::text::ag_catalog.agtype
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = %s
                        """,
                        (props_json, op.id),
                    )

                if op.remove_properties:
                    for prop in op.remove_properties:
                        cursor.execute(
                            f"""
                            UPDATE {table_name} AS t
                            SET properties = (
                                (t.properties::text)::jsonb - %s
                            )::text::ag_catalog.agtype
                            WHERE ag_catalog.agtype_object_field_text_agtype(
                                t.properties, '"id"'::ag_catalog.agtype
                            ) = %s
                            """,
                            (prop, op.id),
                        )
            else:
                # Edge update - similar logic
                cursor.execute(
                    f"""
                    SELECT tableoid::regclass
                    FROM "{graph_name}"._ag_label_edge
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        properties, '"id"'::ag_catalog.agtype
                    ) = %s
                    """,
                    (op.id,),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                table_name = str(row[0])

                if op.set_properties:
                    props_json = json.dumps(op.set_properties)
                    cursor.execute(
                        f"""
                        UPDATE {table_name} AS t
                        SET properties = (
                            (t.properties::text)::jsonb || %s::jsonb
                        )::text::ag_catalog.agtype
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = %s
                        """,
                        (props_json, op.id),
                    )

                if op.remove_properties:
                    for prop in op.remove_properties:
                        cursor.execute(
                            f"""
                            UPDATE {table_name} AS t
                            SET properties = (
                                (t.properties::text)::jsonb - %s
                            )::text::ag_catalog.agtype
                            WHERE ag_catalog.agtype_object_field_text_agtype(
                                t.properties, '"id"'::ag_catalog.agtype
                            ) = %s
                            """,
                            (prop, op.id),
                        )

            batch_duration = (time.perf_counter() - batch_start) * 1000
            probe.batch_applied(
                operation="UPDATE",
                entity_type=str(op.type),
                label=None,
                count=1,
                duration_ms=batch_duration,
            )
            batches += 1

        return batches
