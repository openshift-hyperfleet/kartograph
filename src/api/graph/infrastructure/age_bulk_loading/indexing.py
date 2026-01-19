"""Apache AGE index creation strategy.

Creates PostgreSQL indexes optimized for AGE graph operations within
the caller's transaction for atomicity.
"""

from __future__ import annotations

from typing import Any

from psycopg2 import sql

from graph.domain.value_objects import EntityType
from graph.ports.protocols import TransactionalIndexingProtocol

from .utils import validate_label_name


class AgeIndexingStrategy(TransactionalIndexingProtocol):
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
