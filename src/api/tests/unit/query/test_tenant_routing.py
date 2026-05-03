"""Unit tests for per-tenant graph routing.

Spec: specs/query/query-execution.spec.md
Requirement: Per-Tenant Graph Routing

The system SHALL route all queries to the caller's tenant-specific AGE graph.
"""

from __future__ import annotations

import pytest

from query.domain.value_objects import (
    QueryExecutionError,
    QueryResultRow,
)
from query.infrastructure.tenant_routing import TenantAwareQueryGraphRepository


# ---------------------------------------------------------------------------
# Fakes (no MagicMock — spec-compliant fakes as per testing.spec.md)
# ---------------------------------------------------------------------------


class FakeInnerRepository:
    """Fake IQueryGraphRepository implementation that records calls."""

    def __init__(
        self,
        result: list[QueryResultRow] | None = None,
        raises: Exception | None = None,
    ):
        self.executed_queries: list[str] = []
        self.called_with_timeout: list[int] = []
        self.called_with_max_rows: list[int] = []
        self._result = result or []
        self._raises = raises

    def execute_cypher(
        self,
        query: str,
        timeout_seconds: int = 30,
        max_rows: int = 1000,
    ) -> list[QueryResultRow]:
        self.executed_queries.append(query)
        self.called_with_timeout.append(timeout_seconds)
        self.called_with_max_rows.append(max_rows)
        if self._raises is not None:
            raise self._raises
        return self._result


class FakeGraphExistenceChecker:
    """Fake existence checker that controls which graphs 'exist'."""

    def __init__(self, existing_graphs: set[str] | None = None):
        self._existing = existing_graphs or set()
        self.checked_names: list[str] = []

    def __call__(self, graph_name: str) -> bool:
        self.checked_names.append(graph_name)
        return graph_name in self._existing


# ---------------------------------------------------------------------------
# Tests — Per-Tenant Graph Routing requirement
# ---------------------------------------------------------------------------


class TestTenantAwareQueryGraphRepository:
    """Tests for TenantAwareQueryGraphRepository."""

    def _make_repo(
        self,
        tenant_id: str = "tenant-abc",
        existing_graphs: set[str] | None = None,
        inner_result: list[QueryResultRow] | None = None,
        inner_raises: Exception | None = None,
    ) -> tuple[
        TenantAwareQueryGraphRepository, FakeInnerRepository, FakeGraphExistenceChecker
    ]:
        inner = FakeInnerRepository(result=inner_result, raises=inner_raises)
        checker = FakeGraphExistenceChecker(existing_graphs=existing_graphs)
        repo = TenantAwareQueryGraphRepository(
            tenant_id=tenant_id,
            inner_repository=inner,
            existence_check_fn=checker,
        )
        return repo, inner, checker

    # -----------------------------------------------------------------------
    # Scenario: Query routed to tenant graph
    # -----------------------------------------------------------------------

    def test_routes_query_to_tenant_graph(self):
        """GIVEN an authenticated query request WHEN the query is executed
        THEN it executes against the AGE graph named tenant_{tenant_id}.

        The routing is validated by checking which graph name the
        existence checker is asked about, and by verifying the inner
        repository is called (i.e. the query reached the DB via the
        correctly-routed path).
        """
        tenant_id = "01ARZ3NDEK"
        expected_graph_name = f"tenant_{tenant_id}"

        repo, inner, checker = self._make_repo(
            tenant_id=tenant_id,
            existing_graphs={expected_graph_name},
        )

        repo.execute_cypher("MATCH (n) RETURN n")

        # The existence check must have been performed for the tenant graph
        assert expected_graph_name in checker.checked_names

        # The inner repository (which is connected to the tenant graph) was called
        assert len(inner.executed_queries) == 1
        assert inner.executed_queries[0] == "MATCH (n) RETURN n"

    def test_graph_name_format_is_tenant_prefix_plus_id(self):
        """Spec: AGE graph named `tenant_{tenant_id}` for the resolved tenant."""
        tenant_id = "12345"
        repo, inner, checker = self._make_repo(
            tenant_id=tenant_id,
            existing_graphs={"tenant_12345"},
        )
        repo.execute_cypher("MATCH (n) RETURN n")

        # Must check specifically 'tenant_{tenant_id}'
        assert checker.checked_names == ["tenant_12345"]

    def test_different_tenants_check_different_graphs(self):
        """Queries never cross tenant boundaries."""
        repo_a, inner_a, checker_a = self._make_repo(
            tenant_id="tenant-a",
            existing_graphs={"tenant_tenant-a"},
        )
        repo_b, inner_b, checker_b = self._make_repo(
            tenant_id="tenant-b",
            existing_graphs={"tenant_tenant-b"},
        )

        repo_a.execute_cypher("MATCH (n) RETURN n")
        repo_b.execute_cypher("MATCH (n) RETURN n")

        assert checker_a.checked_names == ["tenant_tenant-a"]
        assert checker_b.checked_names == ["tenant_tenant-b"]

    def test_passes_results_through_from_inner_repository(self):
        """Should return results from the inner repository unchanged."""
        expected_results: list[QueryResultRow] = [{"value": 42}, {"name": "Alice"}]

        repo, inner, _ = self._make_repo(
            existing_graphs={"tenant_tenant-abc"},
            inner_result=expected_results,
        )

        results = repo.execute_cypher("MATCH (n) RETURN n")

        assert results == expected_results

    def test_passes_timeout_to_inner_repository(self):
        """Should forward timeout_seconds to the inner repository."""
        repo, inner, _ = self._make_repo(existing_graphs={"tenant_tenant-abc"})

        repo.execute_cypher("MATCH (n) RETURN n", timeout_seconds=15)

        assert inner.called_with_timeout == [15]

    def test_passes_max_rows_to_inner_repository(self):
        """Should forward max_rows to the inner repository."""
        repo, inner, _ = self._make_repo(existing_graphs={"tenant_tenant-abc"})

        repo.execute_cypher("MATCH (n) RETURN n", max_rows=500)

        assert inner.called_with_max_rows == [500]

    def test_uses_default_timeout_if_not_specified(self):
        """Should use default timeout when not explicitly provided."""
        repo, inner, _ = self._make_repo(existing_graphs={"tenant_tenant-abc"})

        repo.execute_cypher("MATCH (n) RETURN n")

        assert inner.called_with_timeout == [30]

    def test_uses_default_max_rows_if_not_specified(self):
        """Should use default max_rows when not explicitly provided."""
        repo, inner, _ = self._make_repo(existing_graphs={"tenant_tenant-abc"})

        repo.execute_cypher("MATCH (n) RETURN n")

        assert inner.called_with_max_rows == [1000]

    # -----------------------------------------------------------------------
    # Scenario: Tenant graph not found
    # -----------------------------------------------------------------------

    def test_raises_execution_error_when_tenant_graph_not_found(self):
        """GIVEN a tenant whose AGE graph has not been provisioned
        WHEN a query is submitted
        THEN the request is rejected with an execution error before reaching the database.
        """
        repo, inner, _ = self._make_repo(
            tenant_id="unprovisioned",
            existing_graphs=set(),  # no graphs exist
        )

        with pytest.raises(QueryExecutionError):
            repo.execute_cypher("MATCH (n) RETURN n")

    def test_inner_repository_not_called_when_graph_not_found(self):
        """Should NOT reach the database when tenant graph is not found (spec: before reaching the database)."""
        repo, inner, _ = self._make_repo(
            tenant_id="unprovisioned",
            existing_graphs=set(),
        )

        with pytest.raises(QueryExecutionError):
            repo.execute_cypher("MATCH (n) RETURN n")

        # The inner repository (database) must NOT have been called
        assert len(inner.executed_queries) == 0, (
            "Inner repository was called, but spec requires rejection "
            "'before reaching the database'."
        )

    def test_error_message_references_tenant_graph(self):
        """Error message should indicate which graph was not found."""
        tenant_id = "missing-tenant"
        repo, inner, _ = self._make_repo(
            tenant_id=tenant_id,
            existing_graphs=set(),
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            repo.execute_cypher("MATCH (n) RETURN n")

        # Error must somehow reference the tenant to help with debugging
        error_str = str(exc_info.value).lower()
        assert "tenant" in error_str or "graph" in error_str or "provision" in error_str

    def test_graph_not_found_check_happens_before_query_validation(self):
        """Graph existence check should be the FIRST safeguard applied.

        The inner repository validates read-only constraints, LIMIT, etc.
        But if the graph doesn't exist, we should reject before any of that.
        """
        repo, inner, _ = self._make_repo(
            tenant_id="missing",
            existing_graphs=set(),
        )

        # Even a valid read-only query should be rejected if graph not found
        with pytest.raises(QueryExecutionError):
            repo.execute_cypher("MATCH (n) RETURN n")

        assert len(inner.executed_queries) == 0

    def test_only_rejects_missing_graph_not_valid_tenant(self):
        """Should NOT reject when the tenant graph DOES exist."""
        tenant_id = "valid-tenant"
        repo, inner, _ = self._make_repo(
            tenant_id=tenant_id,
            existing_graphs={"tenant_valid-tenant"},
        )

        # Should NOT raise - graph exists
        repo.execute_cypher("MATCH (n) RETURN n")
        assert len(inner.executed_queries) == 1

    def test_existence_check_uses_correct_graph_name_format(self):
        """The existence check must use 'tenant_{tenant_id}' format.

        Ensure we don't check just tenant_id or some other variation.
        """
        tenant_id = "abc-123"
        # The existence checker only returns True for the correct full name
        checker = FakeGraphExistenceChecker(existing_graphs={"tenant_abc-123"})
        inner = FakeInnerRepository()
        repo = TenantAwareQueryGraphRepository(
            tenant_id=tenant_id,
            inner_repository=inner,
            existence_check_fn=checker,
        )

        # Should succeed — the checker returns True for "tenant_abc-123"
        repo.execute_cypher("MATCH (n) RETURN n")
        assert len(inner.executed_queries) == 1

        # Verify the checked name is the correct format
        assert "tenant_abc-123" in checker.checked_names
        assert "abc-123" not in checker.checked_names

    # -----------------------------------------------------------------------
    # Implementation interface contract
    # -----------------------------------------------------------------------

    def test_implements_query_graph_repository_interface(self):
        """TenantAwareQueryGraphRepository must implement IQueryGraphRepository."""
        from query.ports.repositories import IQueryGraphRepository

        inner = FakeInnerRepository()
        repo = TenantAwareQueryGraphRepository(
            tenant_id="test",
            inner_repository=inner,
            existence_check_fn=lambda _: True,
        )

        assert isinstance(repo, IQueryGraphRepository)

    def test_propagates_inner_repository_errors(self):
        """Should propagate errors raised by the inner repository."""
        from query.domain.value_objects import QueryForbiddenError

        inner = FakeInnerRepository(
            raises=QueryForbiddenError("Mutation keyword detected")
        )
        repo = TenantAwareQueryGraphRepository(
            tenant_id="test",
            inner_repository=inner,
            existence_check_fn=lambda _: True,
        )

        with pytest.raises(QueryForbiddenError):
            repo.execute_cypher("CREATE (n:Test)")
