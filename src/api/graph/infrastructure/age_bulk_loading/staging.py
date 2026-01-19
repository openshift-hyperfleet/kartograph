"""Staging table management for AGE bulk loading.

Handles temporary staging tables used for PostgreSQL COPY operations
during bulk loading.
"""

from __future__ import annotations

import io
import json
from typing import Any

from psycopg2 import sql

from graph.domain.value_objects import MutationOperation

from .utils import escape_copy_value


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

    def create_edge_resolution_indexes(self, cursor: Any, table_name: str) -> None:
        """Create indexes on start_id and end_id for faster graphid resolution.

        During edge creation, we need to resolve logical node IDs (start_id, end_id)
        to graphids by joining against _ag_label_vertex. Without indexes on the
        staging table, these UPDATE...FROM...WHERE joins are very slow.

        Args:
            cursor: Database cursor
            table_name: Edge staging table name
        """
        # Index on start_id for the first resolution query
        query = sql.SQL("CREATE INDEX {} ON {} (start_id)").format(
            sql.Identifier(f"{table_name}_start_id_idx"),
            sql.Identifier(table_name),
        )
        cursor.execute(query)

        # Index on end_id for the second resolution query
        query = sql.SQL("CREATE INDEX {} ON {} (end_id)").format(
            sql.Identifier(f"{table_name}_end_id_idx"),
            sql.Identifier(table_name),
        )
        cursor.execute(query)

    def create_graphid_lookup_table(
        self, cursor: Any, graph_name: str, session_id: str
    ) -> tuple[str, int]:
        """Create a temporary lookup table for fast graphid resolution.

        Instead of joining against _ag_label_vertex (which scans all inherited
        label tables), we build a flat temp table with just (logical_id, graphid).
        This avoids the overhead of table inheritance during edge resolution.

        Args:
            cursor: Database cursor
            graph_name: Graph name (schema)
            session_id: Unique session identifier for table naming

        Returns:
            Tuple of (table_name, row_count)
        """
        lookup_table = f"_graphid_lookup_{session_id}"

        # Create temp table with logical_id -> graphid mapping from all nodes
        # Using SELECT INTO for a single-pass operation
        query = sql.SQL(
            """
            CREATE TEMP TABLE {} ON COMMIT DROP AS
            SELECT
                ag_catalog.agtype_object_field_text_agtype(
                    properties, '"id"'::ag_catalog.agtype
                ) AS logical_id,
                id AS graphid
            FROM {}._ag_label_vertex
            """
        ).format(sql.Identifier(lookup_table), sql.Identifier(graph_name))
        cursor.execute(query)

        # Get row count
        cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(lookup_table))
        )
        row_count = cursor.fetchone()[0]

        # Create index on logical_id for fast lookups
        query = sql.SQL("CREATE INDEX {} ON {} (logical_id)").format(
            sql.Identifier(f"{lookup_table}_logical_id_idx"),
            sql.Identifier(lookup_table),
        )
        cursor.execute(query)

        return lookup_table, row_count

    def resolve_edge_graphids(
        self,
        cursor: Any,
        table_name: str,
        lookup_table: str,
    ) -> None:
        """Resolve start_id and end_id to graphids using a lookup table.

        This updates the staging table's start_graphid and end_graphid columns
        by joining against a pre-built lookup table (instead of _ag_label_vertex).
        Using two separate UPDATEs avoids a cartesian product when joining on
        both start and end IDs simultaneously.

        Args:
            cursor: Database cursor
            table_name: Edge staging table name
            lookup_table: Graphid lookup table name (from create_graphid_lookup_table)

        Note:
            Edges with unresolvable node IDs will have NULL graphids and be
            detected by check_for_orphaned_edges.
        """
        # Resolve start_graphid using lookup table
        query = sql.SQL(
            """
            UPDATE {} AS s
            SET start_graphid = lk.graphid
            FROM {} AS lk
            WHERE lk.logical_id = s.start_id
            """
        ).format(sql.Identifier(table_name), sql.Identifier(lookup_table))
        cursor.execute(query)

        # Resolve end_graphid using lookup table
        query = sql.SQL(
            """
            UPDATE {} AS s
            SET end_graphid = lk.graphid
            FROM {} AS lk
            WHERE lk.logical_id = s.end_id
            """
        ).format(sql.Identifier(table_name), sql.Identifier(lookup_table))
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
