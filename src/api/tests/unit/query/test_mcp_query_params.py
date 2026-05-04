"""Unit tests for the _clamp_query_params helper in the MCP query tool.

Tests the parameter bounds enforcement extracted from the `query_graph` MCP tool.

Spec references:
  specs/query/mcp-server.spec.md

  - Requirement: Graph Query Tool — Scenario: Query timeout
    "GIVEN a query that exceeds the timeout (default 30 seconds, max 60 seconds)"
    "WHEN the query is executed"
    "THEN it is terminated and returned with error type 'timeout'"

  - Requirement: Graph Query Tool — Scenario: Result limiting
    "GIVEN a query without a LIMIT clause"
    "WHEN the query is executed"
    "THEN a LIMIT is automatically applied (default 1000, max 10000)"
"""

from __future__ import annotations


from query.presentation.mcp import _clamp_query_params


class TestClampQueryParamsTimeoutSeconds:
    """Timeout parameter capped at 60 seconds.

    Spec: Scenario: Query timeout — "max 60 seconds"
    """

    def test_timeout_seconds_within_bounds_is_unchanged(self) -> None:
        """timeout_seconds below the max must pass through unchanged.

        Spec: Default is 30 seconds. Requesting 30 s should stay 30 s.
        """
        timeout, _ = _clamp_query_params(timeout_seconds=30, max_rows=1000)

        assert timeout == 30

    def test_timeout_seconds_at_max_is_unchanged(self) -> None:
        """timeout_seconds equal to the max (60) must pass through unchanged."""
        timeout, _ = _clamp_query_params(timeout_seconds=60, max_rows=1000)

        assert timeout == 60

    def test_timeout_seconds_above_max_is_clamped_to_60(self) -> None:
        """timeout_seconds = 61 must be clamped to 60."""
        timeout, _ = _clamp_query_params(timeout_seconds=61, max_rows=1000)

        assert timeout == 60

    def test_timeout_seconds_far_above_max_is_clamped_to_60(self) -> None:
        """timeout_seconds = 3600 must be clamped to 60."""
        timeout, _ = _clamp_query_params(timeout_seconds=3600, max_rows=1000)

        assert timeout == 60

    def test_timeout_seconds_999_is_clamped_to_60(self) -> None:
        """timeout_seconds = 999 must be clamped to 60."""
        timeout, _ = _clamp_query_params(timeout_seconds=999, max_rows=1000)

        assert timeout == 60

    def test_default_timeout_below_max_is_unchanged(self) -> None:
        """The default timeout (30 s) is below the max and must pass through unchanged."""
        timeout, _ = _clamp_query_params(timeout_seconds=30, max_rows=1000)

        # Default (30 s) is well within the 60 s bound
        assert timeout == 30


class TestClampQueryParamsMaxRows:
    """max_rows parameter capped at 10 000.

    Spec: Scenario: Result limiting — "max 10000"
    """

    def test_max_rows_within_bounds_is_unchanged(self) -> None:
        """max_rows = 1000 is within bounds and must pass through unchanged."""
        _, rows = _clamp_query_params(timeout_seconds=30, max_rows=1000)

        assert rows == 1000

    def test_max_rows_at_max_is_unchanged(self) -> None:
        """max_rows = 10000 equals the max and must pass through unchanged."""
        _, rows = _clamp_query_params(timeout_seconds=30, max_rows=10000)

        assert rows == 10000

    def test_max_rows_above_max_is_clamped(self) -> None:
        """max_rows = 10001 must be clamped to 10000."""
        _, rows = _clamp_query_params(timeout_seconds=30, max_rows=10001)

        assert rows == 10000

    def test_max_rows_far_above_max_is_clamped(self) -> None:
        """max_rows = 99999 must be clamped to 10000."""
        _, rows = _clamp_query_params(timeout_seconds=30, max_rows=99999)

        assert rows == 10000

    def test_default_max_rows_below_max_is_unchanged(self) -> None:
        """The default max_rows (1000) is below the 10000 bound and must pass through."""
        _, rows = _clamp_query_params(timeout_seconds=30, max_rows=1000)

        assert rows == 1000


class TestClampQueryParamsCombined:
    """Both parameters are independently clamped.

    Clamping is independent: each parameter is bounded individually. No interaction
    between timeout_seconds and max_rows.
    """

    def test_both_params_independently_clamped(self) -> None:
        """Oversized timeout (120 s) and rows (50000) must each clamp independently.

        Spec: max 60 s for timeout, max 10000 for rows.
        Result must be (60, 10000) regardless of how far above the cap each input is.
        """
        timeout, rows = _clamp_query_params(timeout_seconds=120, max_rows=50000)

        assert timeout == 60
        assert rows == 10000

    def test_both_params_within_bounds_unchanged(self) -> None:
        """When both params are within bounds neither should be modified."""
        timeout, rows = _clamp_query_params(timeout_seconds=15, max_rows=500)

        assert timeout == 15
        assert rows == 500

    def test_only_timeout_exceeds_max(self) -> None:
        """When only timeout exceeds max, only timeout is clamped; rows stay unchanged."""
        timeout, rows = _clamp_query_params(timeout_seconds=120, max_rows=500)

        assert timeout == 60
        assert rows == 500

    def test_only_max_rows_exceeds_max(self) -> None:
        """When only max_rows exceeds the limit, only rows are clamped; timeout stays."""
        timeout, rows = _clamp_query_params(timeout_seconds=15, max_rows=99999)

        assert timeout == 15
        assert rows == 10000


class TestClampQueryParamsCustomLimits:
    """Custom override limits work correctly.

    The helper exposes max_timeout and max_limit as keyword parameters so that
    callers (and tests) can inject alternative bounds without monkey-patching.
    """

    def test_custom_max_timeout_is_respected(self) -> None:
        """When max_timeout is overridden, the custom limit is enforced."""
        timeout, _ = _clamp_query_params(
            timeout_seconds=100, max_rows=1000, max_timeout=90
        )

        assert timeout == 90

    def test_custom_max_limit_is_respected(self) -> None:
        """When max_limit is overridden, the custom limit is enforced."""
        _, rows = _clamp_query_params(timeout_seconds=30, max_rows=5000, max_limit=4000)

        assert rows == 4000

    def test_return_type_is_tuple_of_two_ints(self) -> None:
        """The return value must be a tuple of exactly two integers."""
        result = _clamp_query_params(timeout_seconds=30, max_rows=1000)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)
