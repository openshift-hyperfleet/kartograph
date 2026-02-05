"""Unit tests for API Key service probe.

Following TDD - these tests define the expected behavior for
API key service observability probes.
"""

from unittest.mock import MagicMock

import structlog


class TestAPIKeyServiceProbeProtocol:
    """Tests for APIKeyServiceProbe protocol compliance."""

    def test_default_probe_implements_protocol(self):
        """DefaultAPIKeyServiceProbe should implement the protocol."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )

        probe = DefaultAPIKeyServiceProbe()

        # Should have all required methods
        assert hasattr(probe, "api_key_created")
        assert hasattr(probe, "api_key_creation_failed")
        assert hasattr(probe, "api_key_revoked")
        assert hasattr(probe, "api_key_revocation_failed")
        assert hasattr(probe, "api_key_list_retrieved")
        assert hasattr(probe, "with_context")


class TestDefaultAPIKeyServiceProbeInit:
    """Tests for DefaultAPIKeyServiceProbe initialization."""

    def test_creates_with_default_logger(self):
        """Should create default logger when none provided."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )

        probe = DefaultAPIKeyServiceProbe()

        assert probe._logger is not None

    def test_creates_with_custom_logger(self):
        """Should use provided logger."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )

        custom_logger = structlog.get_logger()
        probe = DefaultAPIKeyServiceProbe(logger=custom_logger)

        assert probe._logger is custom_logger

    def test_stores_context(self):
        """Should store observation context."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )
        from shared_kernel.observability_context import ObservationContext

        context = ObservationContext(
            tenant_id="tenant-123",
            user_id="user-456",
            request_id="req-789",
        )
        probe = DefaultAPIKeyServiceProbe(context=context)

        assert probe._context is context


class TestAPIKeyCreatedLogging:
    """Tests for api_key_created method."""

    def test_logs_api_key_created_info(self):
        """Should log api_key_created at info level."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )

        mock_logger = MagicMock()
        probe = DefaultAPIKeyServiceProbe(logger=mock_logger)

        probe.api_key_created(
            api_key_id="key-123",
            user_id="user-456",
            name="My CI Key",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "api_key_created"
        assert call_args[1]["api_key_id"] == "key-123"
        assert call_args[1]["user_id"] == "user-456"
        assert call_args[1]["name"] == "My CI Key"


class TestAPIKeyCreationFailedLogging:
    """Tests for api_key_creation_failed method."""

    def test_logs_api_key_creation_failed_error(self):
        """Should log api_key_creation_failed at error level."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )

        mock_logger = MagicMock()
        probe = DefaultAPIKeyServiceProbe(logger=mock_logger)

        probe.api_key_creation_failed(
            user_id="user-456",
            error="Duplicate name",
        )

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "api_key_creation_failed"
        assert call_args[1]["user_id"] == "user-456"
        assert call_args[1]["error"] == "Duplicate name"


class TestAPIKeyRevokedLogging:
    """Tests for api_key_revoked method."""

    def test_logs_api_key_revoked_info(self):
        """Should log api_key_revoked at info level."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )

        mock_logger = MagicMock()
        probe = DefaultAPIKeyServiceProbe(logger=mock_logger)

        probe.api_key_revoked(
            api_key_id="key-123",
            user_id="user-456",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "api_key_revoked"
        assert call_args[1]["api_key_id"] == "key-123"
        assert call_args[1]["user_id"] == "user-456"


class TestAPIKeyRevocationFailedLogging:
    """Tests for api_key_revocation_failed method."""

    def test_logs_api_key_revocation_failed_error(self):
        """Should log api_key_revocation_failed at error level."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )

        mock_logger = MagicMock()
        probe = DefaultAPIKeyServiceProbe(logger=mock_logger)

        probe.api_key_revocation_failed(
            api_key_id="key-123",
            error="Key not found",
        )

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "api_key_revocation_failed"
        assert call_args[1]["api_key_id"] == "key-123"
        assert call_args[1]["error"] == "Key not found"


class TestAPIKeyListRetrievedLogging:
    """Tests for api_key_list_retrieved method."""

    def test_logs_api_key_list_retrieved_info(self):
        """Should log api_key_list_retrieved at info level."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )

        mock_logger = MagicMock()
        probe = DefaultAPIKeyServiceProbe(logger=mock_logger)

        probe.api_key_list_retrieved(
            user_id="user-456",
            count=5,
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "api_key_list_retrieved"
        assert call_args[1]["filter_user_id"] == "user-456"
        assert call_args[1]["count"] == 5


class TestWithContext:
    """Tests for with_context method."""

    def test_returns_new_probe_with_context(self):
        """Should return a new probe with context bound."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )
        from shared_kernel.observability_context import ObservationContext

        original_probe = DefaultAPIKeyServiceProbe()
        context = ObservationContext(
            tenant_id="tenant-123",
            user_id="user-456",
            request_id="req-789",
        )

        new_probe = original_probe.with_context(context)

        assert new_probe is not original_probe
        assert new_probe._context is context

    def test_context_included_in_log_calls(self):
        """Should include context in log calls."""
        from iam.application.observability.api_key_service_probe import (
            DefaultAPIKeyServiceProbe,
        )
        from shared_kernel.observability_context import ObservationContext

        mock_logger = MagicMock()
        # Note: context user_id is different from method user_id
        # The method user_id takes precedence (overwrites context user_id)
        context = ObservationContext(
            tenant_id="tenant-123",
            request_id="req-789",
        )
        probe = DefaultAPIKeyServiceProbe(logger=mock_logger, context=context)

        probe.api_key_created(
            api_key_id="key-123",
            user_id="user-456",
            name="Test Key",
        )

        call_args = mock_logger.info.call_args[1]
        assert call_args["tenant_id"] == "tenant-123"
        assert call_args["request_id"] == "req-789"
        assert call_args["user_id"] == "user-456"
