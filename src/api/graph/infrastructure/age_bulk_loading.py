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
from typing import Any

from psycopg2 import sql

from graph.domain.value_objects import EntityType, MutationOperation, MutationResult
from graph.ports.observability import MutationProbe
from graph.ports.protocols import GraphClientProtocol, TransactionalIndexingProtocol


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


class AgeIndexingStrategy:
    """Apache AGE implementation of TransactionalIndexingProtocol.

    Creates PostgreSQL indexes optimized for AGE graph operations:
    - BTREE on id column (graphid) for fast vertex/edge lookups
    - GIN on properties column for property-based Cypher queries
    - BTREE on properties.id for logical ID lookups via direct SQL
    - For edges: BTREE on start_id and end_id for join performance

    All indexes are created within the caller's transaction for atomicity.

    References:
        - https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/generative-ai-age-performance
        - https://github.com/apache/age/issues/2176
    """

    def create_label_indexes(
        self,
        cursor: Any,
        graph_name: str,
        label: str,
        entity_type: EntityType,
    ) -> int:
        """Create indexes for a label using the provided cursor (within transaction).

        Args:
            cursor: Database cursor (within transaction)
            graph_name: Graph name (schema)
            label: Label name (table)
            entity_type: EntityType.NODE or EntityType.EDGE

        Returns:
            Number of indexes created

        Raises:
            ValueError: If graph_name, label, or entity_type are invalid
        """
        # Defense in depth: validate inputs even though callers should pre-validate
        validate_label_name(graph_name)
        validate_label_name(label)

        if not isinstance(entity_type, EntityType):
            raise ValueError(
                f"Invalid entity_type '{entity_type}': must be EntityType.NODE or EntityType.EDGE"
            )

        indexes = self._build_index_definitions(graph_name, label, entity_type)
        return self._create_missing_indexes(cursor, graph_name, indexes)

    def _build_index_definitions(
        self,
        graph_name: str,
        label: str,
        entity_type: EntityType,
    ) -> list[dict[str, Any]]:
        """Build the list of index definitions for a label.

        Args:
            graph_name: Graph name (schema)
            label: Label name (table)
            entity_type: EntityType.NODE or EntityType.EDGE

        Returns:
            List of index definitions with 'name' and 'sql' keys
        """
        indexes = []

        # BTREE on id column (graphid) - critical for all labels
        indexes.append(
            {
                "name": f"idx_{graph_name}_{label}_id_btree",
                "sql": sql.SQL(
                    "CREATE INDEX IF NOT EXISTS {} ON {}.{} USING BTREE (id)"
                ).format(
                    sql.Identifier(f"idx_{graph_name}_{label}_id_btree"),
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                ),
            }
        )

        # GIN on properties column - for property-based queries
        indexes.append(
            {
                "name": f"idx_{graph_name}_{label}_props_gin",
                "sql": sql.SQL(
                    "CREATE INDEX IF NOT EXISTS {} ON {}.{} USING GIN (properties)"
                ).format(
                    sql.Identifier(f"idx_{graph_name}_{label}_props_gin"),
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                ),
            }
        )

        # BTREE on properties.id - for logical ID lookups (CRITICAL for performance)
        # IMPORTANT: Must use agtype_object_field_text_agtype to match the function
        # used in UPDATE/INSERT WHERE clauses, otherwise PostgreSQL won't use the index
        indexes.append(
            {
                "name": f"idx_{graph_name}_{label}_prop_id_text_btree",
                "sql": sql.SQL(
                    "CREATE INDEX IF NOT EXISTS {} ON {}.{} USING BTREE ("
                    "ag_catalog.agtype_object_field_text_agtype(properties, "
                    "'\"id\"'::ag_catalog.agtype))"
                ).format(
                    sql.Identifier(f"idx_{graph_name}_{label}_prop_id_text_btree"),
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                ),
            }
        )

        # Edge-specific indexes
        if entity_type == EntityType.EDGE:
            # BTREE on start_id - for join performance
            indexes.append(
                {
                    "name": f"idx_{graph_name}_{label}_start_id_btree",
                    "sql": sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {} ON {}.{} USING BTREE (start_id)"
                    ).format(
                        sql.Identifier(f"idx_{graph_name}_{label}_start_id_btree"),
                        sql.Identifier(graph_name),
                        sql.Identifier(label),
                    ),
                }
            )
            # BTREE on end_id - for join performance
            indexes.append(
                {
                    "name": f"idx_{graph_name}_{label}_end_id_btree",
                    "sql": sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {} ON {}.{} USING BTREE (end_id)"
                    ).format(
                        sql.Identifier(f"idx_{graph_name}_{label}_end_id_btree"),
                        sql.Identifier(graph_name),
                        sql.Identifier(label),
                    ),
                }
            )

        return indexes

    def _create_missing_indexes(
        self,
        cursor: Any,
        graph_name: str,
        indexes: list[dict[str, Any]],
    ) -> int:
        """Create indexes that don't already exist.

        Args:
            cursor: Database cursor (within transaction)
            graph_name: Graph name (schema) for checking existing indexes
            indexes: List of index definitions with 'name' and 'sql' keys

        Returns:
            Number of indexes created
        """
        created = 0
        for idx in indexes:
            # Check if index already exists
            cursor.execute(
                """
                SELECT 1 FROM pg_indexes
                WHERE schemaname = %s AND indexname = %s
                """,
                (graph_name, idx["name"]),
            )
            if cursor.fetchone() is not None:
                continue

            # Create the index
            cursor.execute(idx["sql"])
            created += 1

        return created


class StagingTableManager:
    """Manages temporary staging tables for bulk COPY operations."""

    def create_node_staging_table(self, cursor: Any, session_id: str) -> str:
        """Create a temporary staging table for nodes."""
        table_name = f"_staging_nodes_{session_id}"
        query = sql.SQL(
            """
            CREATE TEMP TABLE {} (
                id TEXT NOT NULL,
                label TEXT NOT NULL,
                properties JSONB NOT NULL
            ) ON COMMIT DROP
            """
        ).format(sql.Identifier(table_name))
        cursor.execute(query)
        return table_name

    def create_edge_staging_table(self, cursor: Any, session_id: str) -> str:
        """Create a temporary staging table for edges with graphid resolution columns."""
        table_name = f"_staging_edges_{session_id}"
        query = sql.SQL(
            """
            CREATE TEMP TABLE {} (
                id TEXT NOT NULL,
                label TEXT NOT NULL,
                start_id TEXT NOT NULL,
                end_id TEXT NOT NULL,
                start_graphid ag_catalog.graphid,
                end_graphid ag_catalog.graphid,
                properties JSONB NOT NULL
            ) ON COMMIT DROP
            """
        ).format(sql.Identifier(table_name))
        cursor.execute(query)
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
        query = sql.SQL("SELECT DISTINCT label FROM {}").format(
            sql.Identifier(table_name)
        )
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def create_label_index(self, cursor: Any, table_name: str) -> None:
        """Create an index on the label column for faster WHERE label = X queries.

        This is a critical performance optimization. Without this index, every
        INSERT/UPDATE that filters by label does a full sequential scan of the
        entire staging table. With many labels, this means scanning the table
        N times where N = number of labels.

        Args:
            cursor: Database cursor
            table_name: Staging table name
        """
        index_name = f"{table_name}_label_idx"
        query = sql.SQL("CREATE INDEX {} ON {} (label)").format(
            sql.Identifier(index_name),
            sql.Identifier(table_name),
        )
        cursor.execute(query)

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
        query = sql.SQL(
            """
            UPDATE {} AS s
            SET start_graphid = v.id
            FROM {}._ag_label_vertex AS v
            WHERE ag_catalog.agtype_object_field_text_agtype(
                      v.properties, '"id"'::ag_catalog.agtype
                  ) = s.start_id
            """
        ).format(sql.Identifier(table_name), sql.Identifier(graph_name))
        cursor.execute(query)

        # Resolve end_graphid separately to avoid cartesian join
        query = sql.SQL(
            """
            UPDATE {} AS s
            SET end_graphid = v.id
            FROM {}._ag_label_vertex AS v
            WHERE ag_catalog.agtype_object_field_text_agtype(
                      v.properties, '"id"'::ag_catalog.agtype
                  ) = s.end_id
            """
        ).format(sql.Identifier(table_name), sql.Identifier(graph_name))
        cursor.execute(query)

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
        query = sql.SQL(
            """
            SELECT s.id, s.start_id, s.end_id, s.start_graphid, s.end_graphid
            FROM {} AS s
            WHERE s.start_graphid IS NULL OR s.end_graphid IS NULL
            """
        ).format(sql.Identifier(table_name))
        cursor.execute(query)
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
        query = sql.SQL(
            """
            SELECT id, COUNT(*) as cnt
            FROM {}
            GROUP BY id
            HAVING COUNT(*) > 1
            """
        ).format(sql.Identifier(table_name))
        cursor.execute(query)
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

    def __init__(
        self,
        indexing_strategy: TransactionalIndexingProtocol | None = None,
        batch_size: int | None = None,
    ):
        self._indexing_strategy = indexing_strategy or AgeIndexingStrategy()
        self._batch_size = batch_size or self.DEFAULT_BATCH_SIZE

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
            # Operations are pre-sorted by MutationApplier for referential integrity
            create_nodes = [
                op
                for op in operations
                if op.op == "CREATE" and op.type == EntityType.NODE
            ]
            create_edges = [
                op
                for op in operations
                if op.op == "CREATE" and op.type == EntityType.EDGE
            ]
            delete_edges = [
                op
                for op in operations
                if op.op == "DELETE" and op.type == EntityType.EDGE
            ]
            delete_nodes = [
                op
                for op in operations
                if op.op == "DELETE" and op.type == EntityType.NODE
            ]
            update_ops = [op for op in operations if op.op == "UPDATE"]

            # Execute all operations in a single transaction
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

    def _get_existing_labels(self, cursor: Any, graph_name: str) -> set[str]:
        """Get all existing label names in the graph.

        Returns:
            Set of label names that already exist
        """
        cursor.execute(
            """
            SELECT l.name
            FROM ag_catalog.ag_label l
            JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
            WHERE g.name = %s
            AND l.name NOT LIKE '_ag_label%%'
            """,
            (graph_name,),
        )
        return {row[0] for row in cursor.fetchall()}

    def _pre_create_labels_and_indexes(
        self,
        cursor: Any,
        graph_name: str,
        labels: list[str],
        entity_type: EntityType,
    ) -> set[str]:
        """Pre-create all new labels and their indexes in batch.

        This is a performance optimization that reduces round trips by:
        1. Checking which labels already exist in one query
        2. Creating all new labels in sequence
        3. Creating all indexes for new labels in sequence

        This separates label/index creation from the INSERT/UPDATE loop,
        reducing per-label overhead during the actual data insertion.

        Args:
            cursor: Database cursor
            graph_name: Graph name
            labels: List of labels to ensure exist
            entity_type: EntityType.NODE or EntityType.EDGE

        Returns:
            Set of labels that were newly created (vs already existing)
        """
        # Get all existing labels in one query
        existing_labels = self._get_existing_labels(cursor, graph_name)

        # Determine which labels need to be created
        new_labels = set(labels) - existing_labels

        # Create all new labels
        for label in new_labels:
            if entity_type == EntityType.NODE:
                cursor.execute(
                    "SELECT ag_catalog.create_vlabel(%s, %s)",
                    (graph_name, label),
                )
            else:
                cursor.execute(
                    "SELECT ag_catalog.create_elabel(%s, %s)",
                    (graph_name, label),
                )

        # Create all indexes for new labels
        for label in new_labels:
            self._indexing_strategy.create_label_indexes(
                cursor, graph_name, label, entity_type
            )

        return new_labels

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

        staging_manager = StagingTableManager()
        batches = 0

        # Create staging table and COPY data
        table_name = staging_manager.create_node_staging_table(cursor, session_id)
        staging_manager.copy_nodes_to_staging(
            cursor, table_name, operations, graph_name
        )

        # Create index on staging table's label column for faster WHERE queries
        # This is critical: without it, every INSERT/UPDATE scans the entire staging table
        staging_manager.create_label_index(cursor, table_name)

        # Check for duplicates and fail fast
        staging_manager.check_for_duplicate_ids(cursor, table_name, "node", probe)

        # Get distinct labels and pre-create all new labels/indexes in batch
        labels = staging_manager.fetch_distinct_labels(cursor, table_name)
        new_labels = self._pre_create_labels_and_indexes(
            cursor, graph_name, labels, EntityType.NODE
        )

        # Process each label (now just INSERT/UPDATE, no label/index creation)
        for label in labels:
            batch_start = time.perf_counter()
            is_new_label = label in new_labels

            # Get label info (should always exist now)
            label_info = self._get_label_info(cursor, graph_name, label)

            if label_info is None:
                raise ValueError(f"Label '{label}' not found in graph '{graph_name}'")

            label_id, seq_name = label_info

            # Build sequence name for nextval() with proper quoting
            # nextval() expects a text argument containing the properly-quoted identifier
            # Format: '"schema_name"."sequence_name"' (quotes inside the string literal)
            seq_literal = sql.Literal(f'"{graph_name}"."{seq_name}"')

            if is_new_label:
                # For new labels, the table is empty - no need for UPDATE or NOT EXISTS
                # This is a significant performance optimization
                updated = 0
                query = sql.SQL(
                    """
                    INSERT INTO {}.{} (id, properties)
                    SELECT
                        ag_catalog._graphid(%s, nextval({})),
                        (s.properties::text)::ag_catalog.agtype
                    FROM {} AS s
                    WHERE s.label = %s
                    """
                ).format(
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                    seq_literal,
                    sql.Identifier(table_name),
                )
                cursor.execute(query, (label_id, label))
                inserted = cursor.rowcount
            else:
                # For existing labels, we need UPDATE for idempotency and
                # NOT EXISTS to avoid duplicate inserts
                query = sql.SQL(
                    """
                    UPDATE {}.{} AS t
                    SET properties = (s.properties::text)::ag_catalog.agtype
                    FROM {} AS s
                    WHERE s.label = %s
                    AND ag_catalog.agtype_object_field_text_agtype(
                        t.properties, '"id"'::ag_catalog.agtype
                    ) = s.id
                    """
                ).format(
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                    sql.Identifier(table_name),
                )
                cursor.execute(query, (label,))
                updated = cursor.rowcount

                query = sql.SQL(
                    """
                    INSERT INTO {}.{} (id, properties)
                    SELECT
                        ag_catalog._graphid(%s, nextval({})),
                        (s.properties::text)::ag_catalog.agtype
                    FROM {} AS s
                    WHERE s.label = %s
                    AND NOT EXISTS (
                        SELECT 1 FROM {}.{} AS t
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = s.id
                    )
                    """
                ).format(
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                    seq_literal,
                    sql.Identifier(table_name),
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                )
                cursor.execute(query, (label_id, label))
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
        # Validate all label names before processing to prevent SQL injection
        for op in operations:
            if op.label:
                validate_label_name(op.label)

        staging_manager = StagingTableManager()
        batches = 0

        # Create staging table and COPY data
        table_name = staging_manager.create_edge_staging_table(cursor, session_id)
        staging_manager.copy_edges_to_staging(
            cursor, table_name, operations, graph_name
        )

        # Create index on staging table's label column for faster WHERE queries
        # This is critical: without it, every INSERT/UPDATE scans the entire staging table
        staging_manager.create_label_index(cursor, table_name)

        # Pre-resolve graphids in batch operations (major performance win)
        staging_manager.resolve_edge_graphids(cursor, table_name, graph_name)

        # Check for orphaned edges (referencing non-existent nodes) and fail fast
        staging_manager.check_for_orphaned_edges(cursor, table_name, probe)

        # Check for duplicates and fail fast
        staging_manager.check_for_duplicate_ids(cursor, table_name, "edge", probe)

        # Get distinct labels and pre-create all new labels/indexes in batch
        labels = staging_manager.fetch_distinct_labels(cursor, table_name)
        new_labels = self._pre_create_labels_and_indexes(
            cursor, graph_name, labels, EntityType.EDGE
        )

        # Process each label (now just INSERT/UPDATE, no label/index creation)
        for label in labels:
            batch_start = time.perf_counter()
            is_new_label = label in new_labels

            # Get label info (should always exist now)
            label_info = self._get_label_info(cursor, graph_name, label)

            if label_info is None:
                raise ValueError(
                    f"Edge label '{label}' not found in graph '{graph_name}'"
                )

            label_id, seq_name = label_info

            # Build sequence name for nextval() with proper quoting
            # nextval() expects a text argument containing the properly-quoted identifier
            # Format: '"schema_name"."sequence_name"' (quotes inside the string literal)
            seq_literal = sql.Literal(f'"{graph_name}"."{seq_name}"')

            if is_new_label:
                # For new labels, the table is empty - no need for UPDATE or NOT EXISTS
                # This is a significant performance optimization
                updated = 0
                query = sql.SQL(
                    """
                    INSERT INTO {}.{} (id, start_id, end_id, properties)
                    SELECT
                        ag_catalog._graphid(%s, nextval({})),
                        s.start_graphid,
                        s.end_graphid,
                        (s.properties::text)::ag_catalog.agtype
                    FROM {} AS s
                    WHERE s.label = %s
                    AND s.start_graphid IS NOT NULL
                    AND s.end_graphid IS NOT NULL
                    """
                ).format(
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                    seq_literal,
                    sql.Identifier(table_name),
                )
                cursor.execute(query, (label_id, label))
                inserted = cursor.rowcount
            else:
                # For existing labels, we need UPDATE for idempotency and
                # NOT EXISTS to avoid duplicate inserts
                query = sql.SQL(
                    """
                    UPDATE {}.{} AS t
                    SET properties = (s.properties::text)::ag_catalog.agtype
                    FROM {} AS s
                    WHERE s.label = %s
                    AND ag_catalog.agtype_object_field_text_agtype(
                        t.properties, '"id"'::ag_catalog.agtype
                    ) = s.id
                    """
                ).format(
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                    sql.Identifier(table_name),
                )
                cursor.execute(query, (label,))
                updated = cursor.rowcount

                query = sql.SQL(
                    """
                    INSERT INTO {}.{} (id, start_id, end_id, properties)
                    SELECT
                        ag_catalog._graphid(%s, nextval({})),
                        s.start_graphid,
                        s.end_graphid,
                        (s.properties::text)::ag_catalog.agtype
                    FROM {} AS s
                    WHERE s.label = %s
                    AND s.start_graphid IS NOT NULL
                    AND s.end_graphid IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM {}.{} AS e
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            e.properties, '"id"'::ag_catalog.agtype
                        ) = s.id
                    )
                    """
                ).format(
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                    seq_literal,
                    sql.Identifier(table_name),
                    sql.Identifier(graph_name),
                    sql.Identifier(label),
                )
                cursor.execute(query, (label_id, label))
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
                query = sql.SQL(
                    """
                    DELETE FROM {}._ag_label_edge
                    WHERE start_id IN (
                        SELECT id FROM {}._ag_label_vertex
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            properties, '"id"'::ag_catalog.agtype
                        ) = ANY(%s)
                    ) OR end_id IN (
                        SELECT id FROM {}._ag_label_vertex
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            properties, '"id"'::ag_catalog.agtype
                        ) = ANY(%s)
                    )
                    """
                ).format(
                    sql.Identifier(graph_name),
                    sql.Identifier(graph_name),
                    sql.Identifier(graph_name),
                )
                cursor.execute(query, (ids, ids))
                # Then delete the nodes themselves
                query = sql.SQL(
                    """
                    DELETE FROM {}._ag_label_vertex
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        properties, '"id"'::ag_catalog.agtype
                    ) = ANY(%s)
                    """
                ).format(sql.Identifier(graph_name))
                cursor.execute(query, (ids,))
            else:
                # Delete edges
                query = sql.SQL(
                    """
                    DELETE FROM {}._ag_label_edge
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        properties, '"id"'::ag_catalog.agtype
                    ) = ANY(%s)
                    """
                ).format(sql.Identifier(graph_name))
                cursor.execute(query, (ids,))

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
                query = sql.SQL(
                    """
                    SELECT tableoid::regclass
                    FROM {}._ag_label_vertex
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        properties, '"id"'::ag_catalog.agtype
                    ) = %s
                    """
                ).format(sql.Identifier(graph_name))
                cursor.execute(query, (op.id,))
                row = cursor.fetchone()
                if not row:
                    continue
                # table_name is from regclass, which is already a safe, quoted identifier
                # We use sql.SQL() to embed it directly since it's trusted system output
                table_name = str(row[0])

                if op.set_properties:
                    # Merge new properties with existing
                    props_json = json.dumps(op.set_properties)
                    # table_name from regclass is pre-formatted (e.g., "graph"."label")
                    # It's safe to use sql.SQL() since it comes from the database itself
                    query = sql.SQL(
                        """
                        UPDATE {} AS t
                        SET properties = (
                            (t.properties::text)::jsonb || %s::jsonb
                        )::text::ag_catalog.agtype
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = %s
                        """
                    ).format(sql.SQL(table_name))
                    cursor.execute(query, (props_json, op.id))

                if op.remove_properties:
                    # Batch remove all properties in a single UPDATE
                    # Using JSONB - TEXT[] syntax for efficient multi-property removal
                    query = sql.SQL(
                        """
                        UPDATE {} AS t
                        SET properties = (
                            (t.properties::text)::jsonb - %s::text[]
                        )::text::ag_catalog.agtype
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = %s
                        """
                    ).format(sql.SQL(table_name))
                    cursor.execute(query, (list(op.remove_properties), op.id))
            else:
                # Edge update - similar logic
                query = sql.SQL(
                    """
                    SELECT tableoid::regclass
                    FROM {}._ag_label_edge
                    WHERE ag_catalog.agtype_object_field_text_agtype(
                        properties, '"id"'::ag_catalog.agtype
                    ) = %s
                    """
                ).format(sql.Identifier(graph_name))
                cursor.execute(query, (op.id,))
                row = cursor.fetchone()
                if not row:
                    continue
                # table_name is from regclass, which is already a safe, quoted identifier
                # We use sql.SQL() to embed it directly since it's trusted system output
                table_name = str(row[0])

                if op.set_properties:
                    props_json = json.dumps(op.set_properties)
                    # table_name from regclass is pre-formatted (e.g., "graph"."label")
                    # It's safe to use sql.SQL() since it comes from the database itself
                    query = sql.SQL(
                        """
                        UPDATE {} AS t
                        SET properties = (
                            (t.properties::text)::jsonb || %s::jsonb
                        )::text::ag_catalog.agtype
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = %s
                        """
                    ).format(sql.SQL(table_name))
                    cursor.execute(query, (props_json, op.id))

                if op.remove_properties:
                    # Batch remove all properties in a single UPDATE
                    # Using JSONB - TEXT[] syntax for efficient multi-property removal
                    query = sql.SQL(
                        """
                        UPDATE {} AS t
                        SET properties = (
                            (t.properties::text)::jsonb - %s::text[]
                        )::text::ag_catalog.agtype
                        WHERE ag_catalog.agtype_object_field_text_agtype(
                            t.properties, '"id"'::ag_catalog.agtype
                        ) = %s
                        """
                    ).format(sql.SQL(table_name))
                    cursor.execute(query, (list(op.remove_properties), op.id))

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
