"""SQL query builder for Apache AGE bulk loading operations.

This class encapsulates all SQL generation and execution for AGE graph operations,
providing a single place to audit and maintain AGE-specific SQL patterns.
"""

from __future__ import annotations

import json
from typing import Any

from psycopg2 import sql

from graph.domain.value_objects import EntityType

from .utils import compute_stable_hash


class AgeQueryBuilder:
    """SQL query builder for Apache AGE operations.

    All methods are static to allow stateless usage. This class serves as
    a namespace for organizing AGE-specific SQL patterns.
    """

    # =========================================================================
    # Label Management
    # =========================================================================

    @staticmethod
    def get_label_info(
        cursor: Any, graph_name: str, label: str
    ) -> tuple[int, str] | None:
        """Get label_id and sequence name for a label.

        Args:
            cursor: Database cursor
            graph_name: Graph name
            label: Label name

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

    @staticmethod
    def get_existing_labels(cursor: Any, graph_name: str) -> set[str]:
        """Get all existing label names in the graph.

        Args:
            cursor: Database cursor
            graph_name: Graph name

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

    @staticmethod
    def acquire_advisory_lock(cursor: Any, graph_name: str, label: str) -> None:
        """Acquire an advisory lock for a label.

        Uses a stable SHA-256 hash to ensure consistent lock keys
        across Python versions and processes.

        Args:
            cursor: Database cursor
            graph_name: Graph name
            label: Label name
        """
        lock_key = compute_stable_hash(f"{graph_name}:{label}")
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

    @staticmethod
    def create_label(
        cursor: Any, graph_name: str, label: str, entity_type: EntityType
    ) -> None:
        """Create a new vertex or edge label.

        Args:
            cursor: Database cursor
            graph_name: Graph name
            label: Label name to create
            entity_type: EntityType.NODE or EntityType.EDGE
        """
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

    # =========================================================================
    # CREATE Operations (INSERT/UPDATE from staging tables)
    # =========================================================================

    @staticmethod
    def execute_label_upsert(
        cursor: Any,
        graph_name: str,
        label: str,
        label_id: int,
        seq_name: str,
        staging_table: str,
        entity_type: EntityType,
        is_new_label: bool,
    ) -> tuple[int, int]:
        """Execute INSERT/UPDATE operations for a single label.

        This encapsulates the common pattern of:
        - For new labels: just INSERT (table is empty)
        - For existing labels: UPDATE existing, then INSERT new with NOT EXISTS

        Args:
            cursor: Database cursor
            graph_name: Graph name (schema)
            label: Label name (table)
            label_id: AGE label ID for graphid generation
            seq_name: Sequence name for graphid generation
            staging_table: Staging table name
            entity_type: EntityType.NODE or EntityType.EDGE
            is_new_label: Whether this is a newly created label

        Returns:
            Tuple of (updated_count, inserted_count)
        """
        if is_new_label:
            query = AgeQueryBuilder._build_insert_new_label_query(
                graph_name, label, staging_table, seq_name, entity_type
            )
            cursor.execute(query, (label_id, label))
            return 0, cursor.rowcount
        else:
            update_query = AgeQueryBuilder._build_update_existing_query(
                graph_name, label, staging_table
            )
            cursor.execute(update_query, (label,))
            updated = cursor.rowcount

            insert_query = AgeQueryBuilder._build_insert_existing_label_query(
                graph_name, label, staging_table, seq_name, entity_type
            )
            cursor.execute(insert_query, (label_id, label))
            inserted = cursor.rowcount

            return updated, inserted

    @staticmethod
    def _build_update_existing_query(
        graph_name: str,
        label: str,
        staging_table: str,
    ) -> sql.Composed:
        """Build UPDATE query for merging properties on existing entities."""
        return sql.SQL(
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
            sql.Identifier(staging_table),
        )

    @staticmethod
    def _build_insert_new_label_query(
        graph_name: str,
        label: str,
        staging_table: str,
        seq_name: str,
        entity_type: EntityType,
    ) -> sql.Composed:
        """Build INSERT query for new labels (empty tables)."""
        seq_literal = sql.Literal(f'"{graph_name}"."{seq_name}"')

        if entity_type == EntityType.NODE:
            return sql.SQL(
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
                sql.Identifier(staging_table),
            )
        else:
            return sql.SQL(
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
                sql.Identifier(staging_table),
            )

    @staticmethod
    def _build_insert_existing_label_query(
        graph_name: str,
        label: str,
        staging_table: str,
        seq_name: str,
        entity_type: EntityType,
    ) -> sql.Composed:
        """Build INSERT query for existing labels with NOT EXISTS check."""
        seq_literal = sql.Literal(f'"{graph_name}"."{seq_name}"')

        if entity_type == EntityType.NODE:
            return sql.SQL(
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
                sql.Identifier(staging_table),
                sql.Identifier(graph_name),
                sql.Identifier(label),
            )
        else:
            return sql.SQL(
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
                sql.Identifier(staging_table),
                sql.Identifier(graph_name),
                sql.Identifier(label),
            )

    # =========================================================================
    # DELETE Operations
    # =========================================================================

    @staticmethod
    def delete_nodes_with_detach(cursor: Any, graph_name: str, ids: list[str]) -> int:
        """Delete nodes and their connected edges (DETACH DELETE semantics).

        WARNING: This directly manipulates AGE's internal parent tables
        (_ag_label_vertex, _ag_label_edge). It relies on PostgreSQL table
        inheritance where all label-specific tables inherit from parent tables.

        Args:
            cursor: Database cursor
            graph_name: Graph name
            ids: List of logical node IDs to delete

        Returns:
            Number of nodes deleted
        """
        # First delete connected edges
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

        # Then delete the nodes
        query = sql.SQL(
            """
            DELETE FROM {}._ag_label_vertex
            WHERE ag_catalog.agtype_object_field_text_agtype(
                properties, '"id"'::ag_catalog.agtype
            ) = ANY(%s)
            """
        ).format(sql.Identifier(graph_name))
        cursor.execute(query, (ids,))
        return cursor.rowcount

    @staticmethod
    def delete_edges(cursor: Any, graph_name: str, ids: list[str]) -> int:
        """Delete edges by their logical IDs.

        Args:
            cursor: Database cursor
            graph_name: Graph name
            ids: List of logical edge IDs to delete

        Returns:
            Number of edges deleted
        """
        query = sql.SQL(
            """
            DELETE FROM {}._ag_label_edge
            WHERE ag_catalog.agtype_object_field_text_agtype(
                properties, '"id"'::ag_catalog.agtype
            ) = ANY(%s)
            """
        ).format(sql.Identifier(graph_name))
        cursor.execute(query, (ids,))
        return cursor.rowcount

    # =========================================================================
    # UPDATE Operations
    # =========================================================================

    @staticmethod
    def find_entity_table(
        cursor: Any, graph_name: str, entity_id: str, entity_type: EntityType
    ) -> str | None:
        """Find the actual label table for an entity by its logical ID.

        Args:
            cursor: Database cursor
            graph_name: Graph name
            entity_id: Logical entity ID
            entity_type: EntityType.NODE or EntityType.EDGE

        Returns:
            Table name as returned by regclass (e.g., '"graph"."label"'), or None
        """
        parent_table = (
            "_ag_label_vertex" if entity_type == EntityType.NODE else "_ag_label_edge"
        )
        query = sql.SQL(
            """
            SELECT tableoid::regclass
            FROM {}.{}
            WHERE ag_catalog.agtype_object_field_text_agtype(
                properties, '"id"'::ag_catalog.agtype
            ) = %s
            """
        ).format(sql.Identifier(graph_name), sql.Identifier(parent_table))
        cursor.execute(query, (entity_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return str(row[0])

    @staticmethod
    def update_properties(
        cursor: Any, table_name: str, entity_id: str, properties: dict[str, Any]
    ) -> None:
        """Merge new properties into an entity's existing properties.

        Args:
            cursor: Database cursor
            table_name: Fully qualified table name from regclass
            entity_id: Logical entity ID
            properties: Properties to merge
        """
        props_json = json.dumps(properties)
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
        cursor.execute(query, (props_json, entity_id))

    @staticmethod
    def remove_properties(
        cursor: Any, table_name: str, entity_id: str, property_names: list[str]
    ) -> None:
        """Remove properties from an entity.

        Args:
            cursor: Database cursor
            table_name: Fully qualified table name from regclass
            entity_id: Logical entity ID
            property_names: Names of properties to remove
        """
        # table_name from regclass is pre-formatted (e.g., "graph"."label")
        # It's safe to use sql.SQL() since it comes from the database itself
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
        cursor.execute(query, (property_names, entity_id))

    # =========================================================================
    # Utility Queries
    # =========================================================================

    @staticmethod
    def count_resolved_edges(cursor: Any, staging_table: str) -> int:
        """Count edges with resolved graphids in a staging table.

        Args:
            cursor: Database cursor
            staging_table: Edge staging table name

        Returns:
            Number of edges with non-null start_graphid
        """
        cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {} WHERE start_graphid IS NOT NULL").format(
                sql.Identifier(staging_table)
            )
        )
        return cursor.fetchone()[0]
