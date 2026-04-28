"""Unit tests for outbox exception types (TDD - tests first).

Spec coverage:
- Requirement: Event Fan-Out — Unknown event type scenario
  "unknown types are permanent failures, not transient"
"""

import pytest

from shared_kernel.outbox.exceptions import UnknownEventTypeError


class TestUnknownEventTypeError:
    """Tests for UnknownEventTypeError exception."""

    def test_is_exception(self):
        """UnknownEventTypeError should be an exception."""
        err = UnknownEventTypeError("SomeEvent", frozenset({"KnownEvent"}))
        assert isinstance(err, Exception)

    def test_carries_unknown_event_type(self):
        """Error should expose the unrecognised event type."""
        err = UnknownEventTypeError("GhostEvent", frozenset({"KnownA", "KnownB"}))
        assert err.event_type == "GhostEvent"

    def test_carries_registered_event_types(self):
        """Error should expose what types ARE registered, for diagnostics."""
        registered = frozenset({"KnownA", "KnownB"})
        err = UnknownEventTypeError("GhostEvent", registered)
        assert err.registered_types == registered

    def test_str_contains_event_type(self):
        """String representation should mention the unknown event type."""
        err = UnknownEventTypeError("GhostEvent", frozenset())
        assert "GhostEvent" in str(err)

    def test_can_be_raised_and_caught(self):
        """UnknownEventTypeError can be raised and caught."""
        with pytest.raises(UnknownEventTypeError) as exc_info:
            raise UnknownEventTypeError("Missing", frozenset({"Present"}))

        assert exc_info.value.event_type == "Missing"

    def test_is_not_value_error(self):
        """UnknownEventTypeError is its own type, separate from ValueError.

        This matters because the worker uses isinstance checks to distinguish
        permanent failures (UnknownEventTypeError) from transient failures.
        """
        err = UnknownEventTypeError("X", frozenset())
        assert not isinstance(err, ValueError)
