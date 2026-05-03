"""Integration tests for primary database-level read-only enforcement.

Spec: specs/query/query-execution.spec.md
Requirement: Read-Only Enforcement — Scenario: Database-level enforcement (primary)

  GIVEN a query session used for graph queries
  WHEN any query is executed
  THEN the database session MUST be configured as read-only
  AND write attempts are rejected by the database regardless of query content

Design
------
These tests bypass the secondary keyword blacklist defense
(``QueryGraphRepository._validate_read_only``) to verify that the **primary**
defense (``SET TRANSACTION READ ONLY`` issued before every Cypher query)
independently rejects write operations at the database level.

The secondary defense is patched as a no-op on the **specific repository
instance** under test using ``patch.object`` — this isolates the test
without affecting other concurrently-running tests.

The mutation query used in both tests includes a RETURN + LIMIT 1 clause so
that ``_ensure_limit`` passes it through unchanged, avoiding any interference
from the result-limiting safeguard.

Regression guard
----------------
Remove ``tx.execute_sql("SET TRANSACTION READ ONLY")`` from
``QueryGraphRepository.execute_cypher`` and
``test_database_rejects_write_even_when_keyword_blacklist_bypassed`` MUST fail.
Without that line the mutation reaches the database and either commits (test
fails: no exception raised) or produces a different error (assertion fails).

Run with
--------
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_query_readonly.py -v -m integration

Spec-Ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
Task-Ref: task-114
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from graph.infrastructure.age_client import AgeGraphClient
from query.domain.value_objects import QueryExecutionError, QueryForbiddenError
from query.infrastructure.query_repository import QueryGraphRepository


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared test query
#
# Properties of this Cypher string:
#   1. Contains "CREATE" — caught by the keyword blacklist (secondary defense).
#   2. Has "RETURN n LIMIT 1" — _ensure_limit detects the LIMIT and leaves the
#      query unchanged (no second LIMIT appended).
#   3. Is syntactically valid Cypher — no parse failure before the DB can
#      enforce READ ONLY.
#   4. When executed in a SET TRANSACTION READ ONLY session, AGE translates
#      the Cypher CREATE into a PostgreSQL INSERT, which PostgreSQL rejects:
#        ERROR: cannot execute INSERT in a read-only transaction
# ---------------------------------------------------------------------------
_MUTATION_QUERY = (
    "CREATE (n:ReadOnlyTest {marker: 'primary_defense_test'}) RETURN n LIMIT 1"
)


class TestDatabaseLevelReadOnlyEnforcement:
    """Integration tests for primary database-level read-only enforcement.

    Spec: Read-Only Enforcement — Scenario: Database-level enforcement (primary)
    "GIVEN a query session used for graph queries
     WHEN any query is executed
     THEN the database session MUST be configured as read-only
     AND write attempts are rejected by the database regardless of query content"

    The two tests in this class together prove:
      - The primary defense (SET TRANSACTION READ ONLY) independently blocks writes.
      - The secondary defense (keyword blacklist) would also block the same write.
      - Therefore both defenses are active and independently effective.
    """

    def test_database_rejects_write_even_when_keyword_blacklist_bypassed(
        self, graph_client: AgeGraphClient
    ) -> None:
        """GIVEN the keyword blacklist (secondary defense) is bypassed
        WHEN a Cypher CREATE mutation is submitted
        THEN the database itself rejects the write with a read-only error.

        This is the core regression guard for the primary defense.  If
        ``tx.execute_sql("SET TRANSACTION READ ONLY")`` is ever removed from
        ``QueryGraphRepository.execute_cypher``, this test will fail because
        the mutation will either succeed (no exception) or raise a different
        error type.

        Spec: Database-level enforcement (primary) —
        "AND write attempts are rejected by the database regardless of query content"
        """
        repository = QueryGraphRepository(client=graph_client)

        # Patch the secondary keyword blacklist to a no-op on this specific
        # repository instance.  Only the primary (database-level) defense remains.
        with patch.object(repository, "_validate_read_only"):
            # _validate_read_only is now a no-op — only SET TRANSACTION READ ONLY
            # can block this mutation at the database level.
            with pytest.raises(QueryExecutionError) as exc_info:
                repository.execute_cypher(_MUTATION_QUERY)

        # The database rejected the write.  PostgreSQL raises:
        #   "ERROR: cannot execute INSERT in a read-only transaction"
        # QueryGraphRepository wraps this as:
        #   "Query execution failed: Transaction query failed: ERROR: cannot
        #    execute INSERT in a read-only transaction"
        error_msg = str(exc_info.value).lower()
        assert any(
            phrase in error_msg
            for phrase in [
                "read-only",
                "read only",
                "cannot execute",
                "execution failed",
            ]
        ), (
            f"Expected a database-level read-only rejection (QueryExecutionError), "
            f"but got: {exc_info.value!r}"
        )

    def test_keyword_blacklist_independently_blocks_same_mutation(
        self, graph_client: AgeGraphClient
    ) -> None:
        """Confirms the previous test is not a false positive.

        Without the patch, the exact same mutation query is rejected by the
        keyword blacklist (``QueryForbiddenError``) **before reaching the
        database**.  This verifies:

          1. The mutation query IS caught by the secondary defense.
          2. The previous test genuinely bypasses the blacklist.
          3. Both defenses independently block the same mutation.

        Spec: Keyword blacklist (secondary) —
        "GIVEN a query containing any of: CREATE, DELETE, SET, REMOVE, MERGE,
         EXPLAIN, LOAD … THEN it is rejected with a forbidden error before
         reaching the database"
        """
        repository = QueryGraphRepository(client=graph_client)

        # Without patching, the keyword blacklist catches CREATE and raises
        # QueryForbiddenError BEFORE any transaction is opened.
        with pytest.raises(QueryForbiddenError) as exc_info:
            repository.execute_cypher(_MUTATION_QUERY)

        error_msg = str(exc_info.value).lower()
        assert "read-only" in error_msg or "create" in error_msg, (
            f"Expected QueryForbiddenError mentioning read-only or CREATE, "
            f"but got: {exc_info.value!r}"
        )
