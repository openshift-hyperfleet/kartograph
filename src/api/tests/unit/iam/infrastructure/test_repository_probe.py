"""Unit tests for IAM repository domain probes."""

from unittest.mock import Mock

from iam.infrastructure.observability import (
    DefaultGroupRepositoryProbe,
    DefaultUserRepositoryProbe,
)


class TestDefaultUserRepositoryProbe:
    """Tests for DefaultUserRepositoryProbe."""

    def test_creates_with_default_logger(self):
        """Test that probe can be created without providing a logger."""
        probe = DefaultUserRepositoryProbe()
        assert probe._logger is not None

    def test_accepts_custom_logger(self):
        """Test that probe accepts a custom logger."""
        custom_logger = Mock()
        probe = DefaultUserRepositoryProbe(logger=custom_logger)
        assert probe._logger is custom_logger


class TestUserSaved:
    """Tests for user_saved probe method."""

    def test_logs_with_correct_parameters(self):
        """Test that user saved event is logged correctly."""
        mock_logger = Mock()
        probe = DefaultUserRepositoryProbe(logger=mock_logger)

        probe.user_saved(user_id="01ABC123", username="alice")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "user_saved"
        assert call_args[1]["user_id"] == "01ABC123"
        assert call_args[1]["username"] == "alice"


class TestUserRetrieved:
    """Tests for user_retrieved probe method."""

    def test_logs_retrieval(self):
        """Test that user retrieval is logged."""
        mock_logger = Mock()
        probe = DefaultUserRepositoryProbe(logger=mock_logger)

        probe.user_retrieved(user_id="01ABC123")

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "user_retrieved"
        assert call_args[1]["user_id"] == "01ABC123"


class TestUserNotFound:
    """Tests for user_not_found probe method."""

    def test_logs_not_found(self):
        """Test that user not found is logged."""
        mock_logger = Mock()
        probe = DefaultUserRepositoryProbe(logger=mock_logger)

        probe.user_not_found(user_id="01ABC123")

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "user_not_found"
        assert call_args[1]["user_id"] == "01ABC123"


class TestUsernameNotFound:
    """Tests for username_not_found probe method."""

    def test_logs_username_not_found(self):
        """Test that username not found is logged."""
        mock_logger = Mock()
        probe = DefaultUserRepositoryProbe(logger=mock_logger)

        probe.username_not_found(username="alice")

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "username_not_found"
        assert call_args[1]["username"] == "alice"


class TestUserProbeWithContext:
    """Tests for with_context method on UserRepositoryProbe."""

    def test_with_context_creates_new_probe(self):
        """Test that with_context creates a new probe instance."""
        probe = DefaultUserRepositoryProbe()
        mock_context = Mock()

        new_probe = probe.with_context(mock_context)

        assert new_probe is not probe
        assert new_probe._context is mock_context

    def test_with_context_preserves_logger(self):
        """Test that with_context preserves the original logger."""
        custom_logger = Mock()
        probe = DefaultUserRepositoryProbe(logger=custom_logger)
        mock_context = Mock()

        new_probe = probe.with_context(mock_context)

        assert new_probe._logger is custom_logger

    def test_context_included_in_log_calls(self):
        """Test that observation context is included in log output."""
        mock_logger = Mock()
        mock_context = Mock()
        mock_context.as_dict.return_value = {
            "request_id": "req-123",
            "correlation_id": "corr-456",
        }

        probe = DefaultUserRepositoryProbe(logger=mock_logger, context=mock_context)

        probe.user_saved(user_id="01ABC123", username="alice")

        call_args = mock_logger.info.call_args
        assert call_args[1]["request_id"] == "req-123"
        assert call_args[1]["correlation_id"] == "corr-456"


class TestDefaultGroupRepositoryProbe:
    """Tests for DefaultGroupRepositoryProbe."""

    def test_creates_with_default_logger(self):
        """Test that probe can be created without providing a logger."""
        probe = DefaultGroupRepositoryProbe()
        assert probe._logger is not None

    def test_accepts_custom_logger(self):
        """Test that probe accepts a custom logger."""
        custom_logger = Mock()
        probe = DefaultGroupRepositoryProbe(logger=custom_logger)
        assert probe._logger is custom_logger


class TestGroupSaved:
    """Tests for group_saved probe method."""

    def test_logs_with_correct_parameters(self):
        """Test that group saved event is logged correctly."""
        mock_logger = Mock()
        probe = DefaultGroupRepositoryProbe(logger=mock_logger)

        probe.group_saved(group_id="01ABC123", tenant_id="01TENANT")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "group_saved"
        assert call_args[1]["group_id"] == "01ABC123"
        assert call_args[1]["tenant_id"] == "01TENANT"


class TestGroupRetrieved:
    """Tests for group_retrieved probe method."""

    def test_logs_with_member_count(self):
        """Test that group retrieval includes member count."""
        mock_logger = Mock()
        probe = DefaultGroupRepositoryProbe(logger=mock_logger)

        probe.group_retrieved(group_id="01ABC123", member_count=5)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "group_retrieved"
        assert call_args[1]["group_id"] == "01ABC123"
        assert call_args[1]["member_count"] == 5


class TestGroupNotFound:
    """Tests for group_not_found probe method."""

    def test_logs_not_found(self):
        """Test that group not found is logged."""
        mock_logger = Mock()
        probe = DefaultGroupRepositoryProbe(logger=mock_logger)

        probe.group_not_found(group_id="01ABC123")

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "group_not_found"
        assert call_args[1]["group_id"] == "01ABC123"


class TestGroupDeleted:
    """Tests for group_deleted probe method."""

    def test_logs_deletion(self):
        """Test that group deletion is logged."""
        mock_logger = Mock()
        probe = DefaultGroupRepositoryProbe(logger=mock_logger)

        probe.group_deleted(group_id="01ABC123")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "group_deleted"
        assert call_args[1]["group_id"] == "01ABC123"


class TestDuplicateGroupName:
    """Tests for duplicate_group_name probe method."""

    def test_logs_duplicate_warning(self):
        """Test that duplicate group name is logged as warning."""
        mock_logger = Mock()
        probe = DefaultGroupRepositoryProbe(logger=mock_logger)

        probe.duplicate_group_name(name="Engineering", tenant_id="01TENANT")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "duplicate_group_name"
        assert call_args[1]["name"] == "Engineering"
        assert call_args[1]["tenant_id"] == "01TENANT"


class TestMembershipHydrationFailed:
    """Tests for membership_hydration_failed probe method."""

    def test_logs_hydration_error(self):
        """Test that hydration failures are logged with error details."""
        mock_logger = Mock()
        probe = DefaultGroupRepositoryProbe(logger=mock_logger)

        probe.membership_hydration_failed(
            group_id="01ABC123", error="SpiceDB connection failed"
        )

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "membership_hydration_failed"
        assert call_args[1]["group_id"] == "01ABC123"
        assert call_args[1]["error"] == "SpiceDB connection failed"


class TestGroupProbeWithContext:
    """Tests for with_context method on GroupRepositoryProbe."""

    def test_with_context_creates_new_probe(self):
        """Test that with_context creates a new probe instance."""
        probe = DefaultGroupRepositoryProbe()
        mock_context = Mock()

        new_probe = probe.with_context(mock_context)

        assert new_probe is not probe
        assert new_probe._context is mock_context

    def test_context_included_in_log_calls(self):
        """Test that observation context is included in log output."""
        mock_logger = Mock()
        mock_context = Mock()
        mock_context.as_dict.return_value = {
            "request_id": "req-456",
            "correlation_id": "corr-789",
        }

        probe = DefaultGroupRepositoryProbe(logger=mock_logger, context=mock_context)

        probe.group_saved(group_id="01ABC123", tenant_id="01TENANT")

        call_args = mock_logger.info.call_args
        assert call_args[1]["request_id"] == "req-456"
        assert call_args[1]["correlation_id"] == "corr-789"
