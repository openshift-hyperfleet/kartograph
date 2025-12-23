"""Unit tests for authorization domain probe."""

from unittest.mock import Mock


from shared_kernel.authorization.observability import (
    DefaultAuthorizationProbe,
)


class TestDefaultAuthorizationProbe:
    """Tests for DefaultAuthorizationProbe."""

    def test_creates_with_default_logger(self):
        """Test that probe can be created without providing a logger."""
        probe = DefaultAuthorizationProbe()
        assert probe._logger is not None

    def test_accepts_custom_logger(self):
        """Test that probe accepts a custom logger."""
        custom_logger = Mock()
        probe = DefaultAuthorizationProbe(logger=custom_logger)
        assert probe._logger is custom_logger


class TestRelationshipWritten:
    """Tests for relationship_written probe method."""

    def test_logs_with_correct_parameters(self):
        """Test that relationship written event is logged correctly."""
        mock_logger = Mock()
        probe = DefaultAuthorizationProbe(logger=mock_logger)

        probe.relationship_written(
            resource="group:abc123",
            relation="member",
            subject="user:alice",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "authorization_relationship_written"
        assert call_args[1]["resource"] == "group:abc123"
        assert call_args[1]["relation"] == "member"
        assert call_args[1]["subject"] == "user:alice"


class TestRelationshipWriteFailed:
    """Tests for relationship_write_failed probe method."""

    def test_logs_error_with_details(self):
        """Test that write failures are logged with error details."""
        mock_logger = Mock()
        probe = DefaultAuthorizationProbe(logger=mock_logger)
        error = ValueError("Connection refused")

        probe.relationship_write_failed(
            resource="group:abc123",
            relation="member",
            subject="user:alice",
            error=error,
        )

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "authorization_relationship_write_failed"
        assert call_args[1]["error"] == "Connection refused"
        assert call_args[1]["error_type"] == "ValueError"


class TestPermissionChecked:
    """Tests for permission_checked probe method."""

    def test_logs_granted_permission(self):
        """Test that granted permissions are logged."""
        mock_logger = Mock()
        probe = DefaultAuthorizationProbe(logger=mock_logger)

        probe.permission_checked(
            resource="group:abc123",
            permission="view",
            subject="user:alice",
            granted=True,
        )

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "authorization_permission_checked"
        assert call_args[1]["granted"] is True

    def test_logs_denied_permission(self):
        """Test that denied permissions are logged."""
        mock_logger = Mock()
        probe = DefaultAuthorizationProbe(logger=mock_logger)

        probe.permission_checked(
            resource="group:abc123",
            permission="delete",
            subject="user:alice",
            granted=False,
        )

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[1]["granted"] is False


class TestBulkCheckCompleted:
    """Tests for bulk_check_completed probe method."""

    def test_logs_bulk_check_statistics(self):
        """Test that bulk check statistics are logged."""
        mock_logger = Mock()
        probe = DefaultAuthorizationProbe(logger=mock_logger)

        probe.bulk_check_completed(
            total_requests=10,
            permitted_count=7,
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "authorization_bulk_check_completed"
        assert call_args[1]["total_requests"] == 10
        assert call_args[1]["permitted_count"] == 7


class TestWithContext:
    """Tests for with_context method."""

    def test_with_context_creates_new_probe(self):
        """Test that with_context creates a new probe instance."""
        probe = DefaultAuthorizationProbe()
        mock_context = Mock()

        new_probe = probe.with_context(mock_context)

        assert new_probe is not probe
        assert new_probe._context is mock_context

    def test_with_context_preserves_logger(self):
        """Test that with_context preserves the original logger."""
        custom_logger = Mock()
        probe = DefaultAuthorizationProbe(logger=custom_logger)
        mock_context = Mock()

        new_probe = probe.with_context(mock_context)

        assert new_probe._logger is custom_logger

    def test_context_included_in_log_calls(self):
        """Test that observation context is included in log output."""
        mock_logger = Mock()
        mock_context = Mock()
        mock_context.as_dict.return_value = {
            "request_id": "req-123",
            "user_id": "user:alice",
        }

        probe = DefaultAuthorizationProbe(logger=mock_logger, context=mock_context)

        probe.relationship_written(
            resource="group:abc123",
            relation="member",
            subject="user:alice",
        )

        call_args = mock_logger.info.call_args
        assert call_args[1]["request_id"] == "req-123"
        assert call_args[1]["user_id"] == "user:alice"
