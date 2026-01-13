"""AGE-specific bulk loading strategy using PostgreSQL COPY protocol.

This strategy optimizes bulk loading for Apache AGE by:
1. Using PostgreSQL COPY to rapidly load data into staging tables
2. Using direct SQL INSERT/UPDATE to write to AGE tables (bypassing slow Cypher MERGE)
3. Computing graphids via AGE's _graphid function and sequences

This approach is ~100x faster than Cypher MERGE for large batches.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
import uuid
from typing import TYPE_CHECKING, Any

from graph.domain.value_objects import EntityType, MutationOperation, MutationResult
from graph.ports.observability import MutationProbe
from graph.ports.protocols import GraphClientProtocol, GraphIndexingProtocol

if TYPE_CHECKING:
    pass


# Label name validation regex: only alphanumeric, underscore, must start with letter or underscore
# Max length 63 (PostgreSQL identifier limit)
_VALID_LABEL_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_MAX_LABEL_LENGTH = 63


def validate_label_name(label: str) -> None:
    """Validate that a label name is safe for use in SQL/Cypher queries.

    Args:
        label: The label name to validate

    Raises:
        ValueError: If the label is empty, too long, or contains invalid characters
    """
    if not label:
        raise ValueError("Invalid label name: label cannot be empty")

    if len(label) > _MAX_LABEL_LENGTH:
        raise ValueError(
            f"Invalid label name '{label}': exceeds maximum length of {_MAX_LABEL_LENGTH} characters"
        )

    if not _VALID_LABEL_PATTERN.match(label):
        raise ValueError(
            f"Invalid label name '{label}': must start with letter or underscore, "
            "and contain only alphanumeric characters and underscores"
        )


def compute_stable_hash(key: str) -> int:
    """Compute a stable hash for advisory lock keys.

    Uses SHA-256 to ensure consistent hashing across Python versions and processes.
    Returns a value that fits within PostgreSQL's signed 64-bit bigint range.

    Args:
        key: The string to hash (typically "graph_name:label")

    Returns:
        A stable integer hash suitable for pg_advisory_xact_lock
    """
    # SHA-256 produces 64 hex characters (256 bits)
    # Take first 16 hex characters (64 bits) and mask to signed 64-bit range
    hash_hex = hashlib.sha256(key.encode()).hexdigest()[:16]
    # Convert to int and mask to ensure it fits in signed 64-bit
    # 0x7FFFFFFFFFFFFFFF ensures non-negative value in signed 64-bit range
    return int(hash_hex, 16) & 0x7FFFFFFFFFFFFFFF


def dict_to_cypher_map(properties: dict) -> str:
    """Convert a Python dict to Cypher map literal format.

    AGE Cypher requires property maps with unquoted keys (Cypher-style),
    not JSON-style with double-quoted keys.

    Cypher format: {key1: "value1", key2: 123}
    JSON format:   {"key1": "value1", "key2": 123}

    Args:
        properties: Python dict to convert

    Returns:
        Cypher map literal string
    """
    import json

    def format_value(v):
        """Format a value for Cypher."""
        if v is None:
            return "null"
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, (int, float)):
            return str(v)
        elif isinstance(v, str):
            # Escape special characters and wrap in double quotes
            escaped = json.dumps(v)  # This handles escaping properly
            return escaped
        elif isinstance(v, dict):
            # Nested map
            return dict_to_cypher_map(v)
        elif isinstance(v, list):
            # List/array
            items = [format_value(item) for item in v]
            return "[" + ", ".join(items) + "]"
        else:
            # Fallback to JSON
            return json.dumps(v)

    pairs = []
    for key, value in properties.items():
        # Keys are unquoted in Cypher (unless they have special chars)
        # For safety, validate keys only contain alphanumeric + underscore
        if not key.replace("_", "").isalnum():
            # Use backticks for special keys
            key = f"`{key}`"
        pairs.append(f"{key}: {format_value(value)}")

    return "{" + ", ".join(pairs) + "}"


def escape_copy_value(value: str) -> str:
    """Escape special characters for PostgreSQL COPY format.

    COPY format uses tab as delimiter and newline as row separator.
    We need to escape these characters in data values.

    Escape sequences for COPY format:
    - Backslash -> \\\\
    - Tab -> \\t
    - Newline -> \\n
    - Carriage return -> \\r

    Args:
        value: The string value to escape

    Returns:
        The escaped string safe for COPY format
    """
    # Order matters: escape backslashes first
    result = value.replace("\\", "\\\\")
    result = result.replace("\t", "\\t")
    result = result.replace("\n", "\\n")
    result = result.replace("\r", "\\r")
    return result


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
        """Create a temporary staging table for edges with graphid resolution columns."""
        table_name = f"_staging_edges_{session_id}"
        cursor.execute(
            f"""
            CREATE TEMP TABLE "{table_name}" (
                id TEXT NOT NULL,
                label TEXT NOT NULL,
                start_id TEXT NOT NULL,
                end_id TEXT NOT NULL,
                start_graphid ag_catalog.graphid,
                end_graphid ag_catalog.graphid,
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
        """COPY node data to staging table using StringIO.

        Uses proper escaping for COPY format to handle tabs, newlines, and
        backslashes in property values.
        """
        buffer = io.StringIO()

        for op in operations:
            props = dict(op.set_properties or {})
            props["id"] = op.id
            props["graph_id"] = graph_name

            # json.dumps already escapes special characters within the JSON,
            # but we also need to escape COPY format special characters
            # (tab, newline, backslash) in the resulting string
            props_json = escape_copy_value(json.dumps(props))
            # Also escape the ID and label fields (these should never be None for CREATE)
            if op.id is None:
                raise ValueError("Node CREATE operation must have an ID")
            if op.label is None:
                raise ValueError("Node CREATE operation must have a label")
            escaped_id = escape_copy_value(op.id)
            escaped_label = escape_copy_value(op.label)
            row = f"{escaped_id}\t{escaped_label}\t{props_json}\n"
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
        """COPY edge data to staging table using StringIO.

        Uses proper escaping for COPY format to handle tabs, newlines, and
        backslashes in property values.
        """
        buffer = io.StringIO()

        for op in operations:
            props = dict(op.set_properties or {})
            props["id"] = op.id
            props["graph_id"] = graph_name

            # json.dumps already escapes special characters within the JSON,
            # but we also need to escape COPY format special characters
            # (tab, newline, backslash) in the resulting string
            props_json = escape_copy_value(json.dumps(props))
            # Also escape the ID, label, start_id, and end_id fields
            # These should never be None for edge CREATE operations
            if op.id is None:
                raise ValueError("Edge CREATE operation must have an ID")
            if op.label is None:
                raise ValueError("Edge CREATE operation must have a label")
            if op.start_id is None:
                raise ValueError("Edge CREATE operation must have a start_id")
            if op.end_id is None:
                raise ValueError("Edge CREATE operation must have an end_id")
            escaped_id = escape_copy_value(op.id)
            escaped_label = escape_copy_value(op.label)
            escaped_start_id = escape_copy_value(op.start_id)
            escaped_end_id = escape_copy_value(op.end_id)
            row = f"{escaped_id}\t{escaped_label}\t{escaped_start_id}\t{escaped_end_id}\t{props_json}\n"
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

    def resolve_edge_graphids(
        self, cursor: Any, table_name: str, graph_name: str
    ) -> None:
        """Resolve start_id and end_id to graphids in two separate batch operations.

        This updates the staging table's start_graphid and end_graphid columns
        by looking up the actual graphids from _ag_label_vertex. Using two
        separate UPDATEs avoids a cartesian product when joining on both
        start and end IDs simultaneously.

        Edges with unresolvable node IDs will have NULL graphids and be
        detected by check_for_orphaned_edges.
        """
        # Resolve start_graphid separately to avoid cartesian join
        cursor.execute(
            f"""
            UPDATE "{table_name}" AS s
            SET start_graphid = v.id
            FROM "{graph_name}"._ag_label_vertex AS v
            WHERE ag_catalog.agtype_object_field_text_agtype(
                      v.properties, '"id"'::ag_catalog.agtype
                  ) = s.start_id
            """
        )

        # Resolve end_graphid separately to avoid cartesian join
        cursor.execute(
            f"""
            UPDATE "{table_name}" AS s
            SET end_graphid = v.id
            FROM "{graph_name}"._ag_label_vertex AS v
            WHERE ag_catalog.agtype_object_field_text_agtype(
                      v.properties, '"id"'::ag_catalog.agtype
                  ) = s.end_id
            """
        )

    def check_for_orphaned_edges(
        self, cursor: Any, table_name: str, probe: Any
    ) -> None:
        """Check for edges that reference non-existent nodes.

        After graphid resolution, edges with NULL start_graphid or end_graphid
        reference nodes that don't exist. This method detects them and raises
        an error instead of silently dropping them.

        Args:
            cursor: Database cursor
            table_name: Edge staging table name
            probe: Mutation probe for observability

        Raises:
            ValueError: If orphaned edges are detected
        """
        cursor.execute(
            f"""
            SELECT s.id, s.start_id, s.end_id, s.start_graphid, s.end_graphid
            FROM "{table_name}" AS s
            WHERE s.start_graphid IS NULL OR s.end_graphid IS NULL
            """
        )
        orphaned = cursor.fetchall()

        if orphaned:
            orphaned_edge_ids = []
            missing_node_ids = set()

            for edge_id, start_id, end_id, start_gid, end_gid in orphaned:
                orphaned_edge_ids.append(edge_id)
                if start_gid is None:
                    missing_node_ids.add(start_id)
                if end_gid is None:
                    missing_node_ids.add(end_id)

            missing_node_ids_list = sorted(missing_node_ids)
            probe.orphaned_edges_detected(orphaned_edge_ids, missing_node_ids_list)

            raise ValueError(
                f"Orphaned edges detected: {len(orphaned_edge_ids)} edge(s) reference "
                f"non-existent nodes. Missing node IDs: {', '.join(missing_node_ids_list[:10])}"
                + (
                    f" (and {len(missing_node_ids_list) - 10} more)"
                    if len(missing_node_ids_list) > 10
                    else ""
                )
            )

    def check_for_duplicate_ids(
        self, cursor: Any, table_name: str, entity_type: str, probe: Any
    ) -> None:
        """Check for duplicate IDs in staging table and raise error if found.

        Args:
            cursor: Database cursor
            table_name: Staging table name
            entity_type: Type of entity ("node" or "edge")
            probe: Mutation probe for observability

        Raises:
            ValueError: If duplicate IDs are found in the batch
        """
        cursor.execute(
            f"""
            SELECT id, COUNT(*) as cnt
            FROM "{table_name}"
            GROUP BY id
            HAVING COUNT(*) > 1
            """
        )
        duplicates = cursor.fetchall()
        if duplicates:
            duplicate_ids = [row[0] for row in duplicates]
            probe.duplicate_ids_detected(duplicate_ids, entity_type)
            raise ValueError(
                f"Duplicate IDs found in batch: {', '.join(duplicate_ids)}. "
                f"Each operation must have a unique ID."
            )


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

            # Phase 1: Ensure indexes exist
            if self._indexing_client is not None:
                self._indexing_client.ensure_all_labels_indexed()

            # Phase 2: Execute all operations in a single transaction
            conn = client.raw_connection
            total_batches = 0

            with conn.cursor() as cursor:
                # Acquire advisory locks for all labels we'll modify
                all_labels = {op.label for op in create_nodes if op.label} | {
                    op.label for op in create_edges if op.label
                }
                self._acquire_label_locks(cursor, graph_name, all_labels)

                # Execute DELETEs first
                if delete_edges:
                    total_batches += self._execute_deletes(
                        cursor, delete_edges, EntityType.EDGE, probe, graph_name
                    )
                if delete_nodes:
                    total_batches += self._execute_deletes(
                        cursor, delete_nodes, EntityType.NODE, probe, graph_name
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
        """Acquire advisory locks for labels to prevent concurrent modifications.

        Uses a stable hash function (SHA-256) to ensure consistent lock keys
        across Python versions and processes.
        """
        for label in labels:
            # Use stable SHA-256 hash instead of Python's unstable hash()
            lock_key = compute_stable_hash(f"{graph_name}:{label}")
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

    def _get_label_info(
        self, cursor: Any, graph_name: str, label: str
    ) -> tuple[int, str] | None:
        """Get label_id and sequence name for a label.

        Returns:
            Tuple of (label_id, seq_name) if label exists, None otherwise
        """
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
            return None
        return (row[0], row[1])

    def _create_label_with_first_entity(
        self, cursor: Any, graph_name: str, label: str, entity_id: str, properties: dict
    ) -> None:
        """Create a new node label by inserting the first entity via Cypher.

        This uses Cypher (via cursor) to create the first entity, which causes
        AGE to automatically create the label table, sequence, and metadata.
        Executes within the current transaction context.

        Args:
            cursor: Database cursor (within transaction)
            graph_name: Graph name
            label: Label to create
            entity_id: ID of first entity
            properties: Properties for first entity
        """
        # Build Cypher CREATE statement with Cypher-style property map
        # AGE Cypher requires unquoted keys, not JSON-style double-quoted keys
        props_str = dict_to_cypher_map(properties)
        cypher = f"CREATE (n:{label} {props_str})"

        # Wrap in AGE's cypher() function and execute via cursor
        # This stays in the transaction unlike client.execute_cypher()
        sql = f"SELECT * FROM cypher('{graph_name}', $$ {cypher} $$) AS (result agtype)"
        cursor.execute(sql)

    def _create_edge_label_with_first_entity(
        self,
        cursor: Any,
        graph_name: str,
        label: str,
        edge_id: str,
        start_id: str,
        end_id: str,
        properties: dict,
    ) -> None:
        """Create a new edge label by inserting the first edge via Cypher.

        This uses Cypher (via cursor) to create the first edge, which causes
        AGE to automatically create the edge label table, sequence, and metadata.
        Executes within the current transaction context.

        Args:
            cursor: Database cursor (within transaction)
            graph_name: Graph name
            label: Edge label to create
            edge_id: ID of first edge
            start_id: Start node ID
            end_id: End node ID
            properties: Properties for first edge
        """
        # Build Cypher CREATE statement with Cypher-style property map
        # AGE Cypher requires unquoted keys, not JSON-style double-quoted keys
        props_str = dict_to_cypher_map(properties)
        cypher = f"""
        MATCH (src {{id: '{start_id}'}}), (tgt {{id: '{end_id}'}})
        CREATE (src)-[r:{label} {props_str}]->(tgt)
        """

        # Wrap in AGE's cypher() function and execute via cursor
        sql = f"SELECT * FROM cypher('{graph_name}', $$ {cypher} $$) AS (result agtype)"
        cursor.execute(sql)

    def _execute_node_creates(
        self,
        cursor: Any,
        operations: list[MutationOperation],
        graph_name: str,
        session_id: str,
        probe: MutationProbe,
    ) -> int:
        """Execute node CREATE operations using direct SQL."""
        # Validate all label names before processing to prevent SQL injection
        for op in operations:
            if op.label:
                validate_label_name(op.label)

        staging_manager = StagingTableManager(graph_name)
        batches = 0

        # Create staging table and COPY data
        table_name = staging_manager.create_node_staging_table(cursor, session_id)
        staging_manager.copy_nodes_to_staging(
            cursor, table_name, operations, graph_name
        )

        # Check for duplicates and fail fast
        staging_manager.check_for_duplicate_ids(cursor, table_name, "node", probe)

        # Process each label
        labels = staging_manager.fetch_distinct_labels(cursor, table_name)

        for label in labels:
            batch_start = time.perf_counter()

            # Check if label exists, create if needed
            label_info = self._get_label_info(cursor, graph_name, label)
            first_entity_id = None  # Track if we created via Cypher
            if label_info is None:
                # Label doesn't exist - create it by inserting first entity via Cypher
                cursor.execute(
                    f"""
                    SELECT id, properties
                    FROM "{table_name}"
                    WHERE label = %s
                    LIMIT 1
                    """,
                    (label,),
                )
                first_row = cursor.fetchone()
                if first_row:
                    first_entity_id, first_props = first_row
                    self._create_label_with_first_entity(
                        cursor, graph_name, label, first_entity_id, first_props
                    )
                    # Now get the label info
                    label_info = self._get_label_info(cursor, graph_name, label)
                    if label_info is None:
                        raise ValueError(f"Failed to create label '{label}'")

            if label_info is None:
                raise ValueError(f"Label '{label}' not found in graph '{graph_name}'")

            label_id, seq_name = label_info

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

            # Insert new nodes (skip first entity if we created it via Cypher)
            if first_entity_id is not None:
                cursor.execute(
                    f"""
                    INSERT INTO "{graph_name}"."{label}" (id, properties)
                    SELECT
                        ag_catalog._graphid(%s, nextval('"{graph_name}"."{seq_name}"')),
                        (s.properties::text)::ag_catalog.agtype
                    FROM "{table_name}" AS s
                    WHERE s.label = %s
                    AND s.id != %s
                    AND NOT EXISTS (
                        SELECT 1 FROM "{graph_name}"."{label}" AS t
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = s.id
                    )
                    """,
                    (label_id, label, first_entity_id),
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO "{graph_name}"."{label}" (id, properties)
                    SELECT
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

            # Account for first entity created via Cypher (not in inserted count)
            cypher_created = 1 if first_entity_id is not None else 0

            batch_duration = (time.perf_counter() - batch_start) * 1000
            probe.batch_applied(
                operation="CREATE",
                entity_type="node",
                label=label,
                count=updated + inserted + cypher_created,
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
        # Validate all label names before processing to prevent SQL injection
        for op in operations:
            if op.label:
                validate_label_name(op.label)

        staging_manager = StagingTableManager(graph_name)
        batches = 0

        # Create staging table and COPY data
        table_name = staging_manager.create_edge_staging_table(cursor, session_id)
        staging_manager.copy_edges_to_staging(
            cursor, table_name, operations, graph_name
        )

        # Pre-resolve graphids in batch operations (major performance win)
        staging_manager.resolve_edge_graphids(cursor, table_name, graph_name)

        # Check for orphaned edges (referencing non-existent nodes) and fail fast
        staging_manager.check_for_orphaned_edges(cursor, table_name, probe)

        # Check for duplicates and fail fast
        staging_manager.check_for_duplicate_ids(cursor, table_name, "edge", probe)

        labels = staging_manager.fetch_distinct_labels(cursor, table_name)

        for label in labels:
            batch_start = time.perf_counter()

            # Check if label exists, create if needed
            label_info = self._get_label_info(cursor, graph_name, label)
            first_edge_id = None  # Track if we created via Cypher
            if label_info is None:
                # Label doesn't exist - create it by inserting first edge via Cypher
                cursor.execute(
                    f"""
                    SELECT id, start_id, end_id, properties
                    FROM "{table_name}"
                    WHERE label = %s
                    LIMIT 1
                    """,
                    (label,),
                )
                first_row = cursor.fetchone()
                if first_row:
                    first_edge_id, start_id, end_id, first_props = first_row
                    self._create_edge_label_with_first_entity(
                        cursor,
                        graph_name,
                        label,
                        first_edge_id,
                        start_id,
                        end_id,
                        first_props,
                    )
                    # Now get the label info
                    label_info = self._get_label_info(cursor, graph_name, label)
                    if label_info is None:
                        raise ValueError(f"Failed to create edge label '{label}'")

            if label_info is None:
                raise ValueError(
                    f"Edge label '{label}' not found in graph '{graph_name}'"
                )

            label_id, seq_name = label_info

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

            # Insert new edges using pre-resolved graphids (skip first if created via Cypher)
            # This is much faster than joining on every INSERT
            if first_edge_id is not None:
                cursor.execute(
                    f"""
                    INSERT INTO "{graph_name}"."{label}" (id, start_id, end_id, properties)
                    SELECT
                        ag_catalog._graphid(%s, nextval('"{graph_name}"."{seq_name}"')),
                        s.start_graphid,
                        s.end_graphid,
                        (s.properties::text)::ag_catalog.agtype
                    FROM "{table_name}" AS s
                    WHERE s.label = %s
                    AND s.id != %s
                    AND s.start_graphid IS NOT NULL
                    AND s.end_graphid IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM "{graph_name}"."{label}" AS e
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            e.properties, '"id"'::ag_catalog.agtype
                        ) = s.id
                    )
                    """,
                    (label_id, label, first_edge_id),
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO "{graph_name}"."{label}" (id, start_id, end_id, properties)
                    SELECT
                        ag_catalog._graphid(%s, nextval('"{graph_name}"."{seq_name}"')),
                        s.start_graphid,
                        s.end_graphid,
                        (s.properties::text)::ag_catalog.agtype
                    FROM "{table_name}" AS s
                    WHERE s.label = %s
                    AND s.start_graphid IS NOT NULL
                    AND s.end_graphid IS NOT NULL
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

            # Account for first edge created via Cypher (not in inserted count)
            cypher_created = 1 if first_edge_id is not None else 0

            batch_duration = (time.perf_counter() - batch_start) * 1000
            probe.batch_applied(
                operation="CREATE",
                entity_type="edge",
                label=label,
                count=updated + inserted + cypher_created,
                duration_ms=batch_duration,
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
        """Execute DELETE operations using direct SQL.

        WARNING: This directly manipulates AGE's internal parent tables
        (_ag_label_vertex, _ag_label_edge). It relies on PostgreSQL table
        inheritance where all label-specific tables (person, project, etc.)
        inherit from these parent tables. Deleting from the parent cascades
        to all child label tables.

        This approach is necessary to maintain transaction atomicity - using
        client.execute_cypher() would auto-commit and break the transaction.

        Fragility considerations:
        - If AGE changes from table inheritance to partitioning/sharding,
          this will break
        - We're using undocumented internal tables (prefixed with _)
        - Property access via agtype_object_field_text_agtype is AGE-specific

        For node deletes, we implement DETACH DELETE semantics by first
        deleting connected edges, then deleting the nodes themselves.
        """
        batches = 0
        for i in range(0, len(operations), self._batch_size):
            batch = operations[i : i + self._batch_size]
            batch_start = time.perf_counter()

            # Build list of IDs to delete
            ids = [op.id for op in batch]

            if entity_type == EntityType.NODE:
                # Delete from parent vertex table (cascades to specific label tables)
                # Note: DETACH DELETE equivalent - first delete connected edges
                cursor.execute(
                    f"""
                    DELETE FROM "{graph_name}"._ag_label_edge
                    WHERE start_id IN (
                        SELECT id FROM "{graph_name}"._ag_label_vertex
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            properties, '"id"'::ag_catalog.agtype
                        ) = ANY(%s)
                    ) OR end_id IN (
                        SELECT id FROM "{graph_name}"._ag_label_vertex
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            properties, '"id"'::ag_catalog.agtype
                        ) = ANY(%s)
                    )
                    """,
                    (ids, ids),
                )
                # Then delete the nodes themselves
                cursor.execute(
                    f"""
                    DELETE FROM "{graph_name}"._ag_label_vertex
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        properties, '"id"'::ag_catalog.agtype
                    ) = ANY(%s)
                    """,
                    (ids,),
                )
            else:
                # Delete edges
                cursor.execute(
                    f"""
                    DELETE FROM "{graph_name}"._ag_label_edge
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        properties, '"id"'::ag_catalog.agtype
                    ) = ANY(%s)
                    """,
                    (ids,),
                )

            deleted = cursor.rowcount
            batch_duration = (time.perf_counter() - batch_start) * 1000

            probe.batch_applied(
                operation="DELETE",
                entity_type=str(entity_type),
                label=None,
                count=deleted,
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
                    # Batch remove all properties in a single UPDATE
                    # Using JSONB - TEXT[] syntax for efficient multi-property removal
                    cursor.execute(
                        f"""
                        UPDATE {table_name} AS t
                        SET properties = (
                            (t.properties::text)::jsonb - %s::text[]
                        )::text::ag_catalog.agtype
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = %s
                        """,
                        (list(op.remove_properties), op.id),
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
                    # Batch remove all properties in a single UPDATE
                    # Using JSONB - TEXT[] syntax for efficient multi-property removal
                    cursor.execute(
                        f"""
                        UPDATE {table_name} AS t
                        SET properties = (
                            (t.properties::text)::jsonb - %s::text[]
                        )::text::ag_catalog.agtype
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = %s
                        """,
                        (list(op.remove_properties), op.id),
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
