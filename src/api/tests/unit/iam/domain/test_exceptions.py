"""Unit tests for IAM domain exceptions.

Tests verify that domain exceptions carry the right semantics and
do not expose internal infrastructure details.
"""

from __future__ import annotations

import pytest

from iam.ports.exceptions import ProvisioningConflictError


class TestProvisioningConflictError:
    """Tests for ProvisioningConflictError exception."""

    def test_is_exception(self):
        """ProvisioningConflictError must be an Exception subclass."""
        error = ProvisioningConflictError("alice")
        assert isinstance(error, Exception)

    def test_stores_conflicting_username(self):
        """Should store the conflicting username for observability."""
        error = ProvisioningConflictError("alice")
        assert error.username == "alice"

    def test_message_does_not_expose_db_internals(self):
        """Error message must not contain database-internal details."""
        error = ProvisioningConflictError("alice")
        message = str(error)
        # Should not contain SQLAlchemy or PostgreSQL terms
        assert "IntegrityError" not in message
        assert "duplicate key" not in message.lower()
        assert "unique constraint" not in message.lower()
        assert "psycopg" not in message.lower()

    def test_message_is_user_friendly(self):
        """Error message should be user-readable."""
        error = ProvisioningConflictError("alice")
        message = str(error)
        assert "alice" in message

    def test_can_be_raised_and_caught(self):
        """Should be raiseable and catchable as ProvisioningConflictError."""
        with pytest.raises(ProvisioningConflictError) as exc_info:
            raise ProvisioningConflictError("bob")
        assert exc_info.value.username == "bob"
