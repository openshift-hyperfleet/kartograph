"""Unit tests for AgeQueryBuilder CREATE idempotent merge behavior.

Spec: "Create an existing node (idempotent merge)"
  THEN existing properties are preserved
  AND new properties from set_properties are added

The _build_update_existing_query method must use jsonb || merge operator,
not simple assignment, so that properties NOT in the new batch are preserved.
"""

from __future__ import annotations

from psycopg2 import sql

from graph.infrastructure.age_bulk_loading.queries import AgeQueryBuilder


def _extract_sql_template(composed: sql.Composed) -> str:  # type: ignore[name-defined]
    """Extract the raw SQL template text from a psycopg2 Composed object.

    Uses only public psycopg2 APIs:
    - Composed.seq  — the ordered list of SQL/Identifier/Composed parts
    - SQL.string    — the raw SQL string fragment
    - Identifier.strings — tuple of identifier name strings

    Identifiers are inlined as quoted names so assertions can check for
    column references (e.g. 't.properties') regardless of schema/table name
    quoting.
    """
    parts: list[str] = []
    for part in composed.seq:
        if isinstance(part, sql.SQL):
            parts.append(part.string)
        elif isinstance(part, sql.Identifier):
            parts.append(".".join('"' + s + '"' for s in part.strings))
        elif isinstance(part, sql.Composed):
            parts.append(_extract_sql_template(part))
        elif isinstance(part, sql.Literal):
            parts.append(str(part.wrapped))
    return "".join(parts)


class TestUpdateExistingQueryMergeSemantics:
    """Tests that _build_update_existing_query uses property merging, not replacement.

    Spec requirement: CREATE on an existing entity must MERGE properties.
    Existing properties not present in the new batch MUST be preserved.
    """

    def test_uses_jsonb_merge_operator_not_simple_assignment(self) -> None:
        """Should use jsonb || merge operator, not simple property replacement.

        The SQL must merge the staging properties INTO the existing properties
        so that existing keys not present in the new batch are preserved.
        """
        query = AgeQueryBuilder._build_update_existing_query(
            graph_name="test_graph",
            label="person",
            staging_table="staging_test",
        )

        sql_text = _extract_sql_template(query)

        assert "||" in sql_text, (
            "UPDATE query must use jsonb || merge operator to preserve existing "
            "properties. Found no '||' in: " + sql_text
        )

    def test_does_not_overwrite_with_staging_properties_alone(self) -> None:
        """Should not overwrite properties with only the staging table value.

        The naive implementation `SET properties = (s.properties::text)::agtype`
        would silently drop any property on the existing entity that isn't
        present in the staging batch. This test ensures that doesn't happen.
        """
        query = AgeQueryBuilder._build_update_existing_query(
            graph_name="test_graph",
            label="person",
            staging_table="staging_test",
        )

        sql_text = _extract_sql_template(query)

        set_clause_start = sql_text.upper().find("SET PROPERTIES")
        assert set_clause_start != -1, "Expected SET properties clause"

        # After SET, the target table (t.properties) MUST appear — this ensures
        # merge, not replacement: (t.properties::text)::jsonb || (s.properties::text)::jsonb
        where_pos = sql_text.upper().find("WHERE")
        set_to_where = sql_text[set_clause_start:where_pos]
        assert "t.properties" in set_to_where, (
            "SET clause must reference existing entity properties (t.properties) "
            "for merge semantics. Got SET clause: " + set_to_where
        )

    def test_references_both_tables_in_set_clause(self) -> None:
        """SET clause should reference both the target and staging properties."""
        query = AgeQueryBuilder._build_update_existing_query(
            graph_name="test_graph",
            label="person",
            staging_table="staging_test",
        )

        sql_text = _extract_sql_template(query)

        set_clause_start = sql_text.upper().find("SET PROPERTIES")
        where_pos = sql_text.upper().find("WHERE")
        set_clause = sql_text[set_clause_start:where_pos]

        # Both t.properties (existing) and s.properties (new) must appear
        assert "t.properties" in set_clause, (
            "Merge must reference existing properties (t.properties): " + set_clause
        )
        assert "s.properties" in set_clause, (
            "Merge must reference staging properties (s.properties): " + set_clause
        )

    def test_uses_correct_graph_and_label_identifiers(self) -> None:
        """Should use the provided graph name and label in SQL identifiers."""
        query = AgeQueryBuilder._build_update_existing_query(
            graph_name="my_graph",
            label="service",
            staging_table="staging_xyz",
        )

        sql_text = _extract_sql_template(query)

        assert "my_graph" in sql_text
        assert "service" in sql_text
        assert "staging_xyz" in sql_text

    def test_merge_consistent_with_update_properties_method(self) -> None:
        """Merge pattern should match the update_properties() method's SQL pattern.

        update_properties() already correctly uses:
            (t.properties::text)::jsonb || %s::jsonb
        _build_update_existing_query should follow the same pattern.
        """
        query = AgeQueryBuilder._build_update_existing_query(
            graph_name="test_graph",
            label="person",
            staging_table="staging_test",
        )

        sql_text = _extract_sql_template(query)

        # Both should use ::jsonb casting for merge
        assert "jsonb" in sql_text, (
            "Merge query should cast to jsonb for || operator, consistent with "
            "update_properties(). SQL: " + sql_text
        )
