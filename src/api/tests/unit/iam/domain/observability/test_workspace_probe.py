"""Unit tests for Workspace domain probe.

Following TDD - these tests define the expected behavior for
workspace aggregate observability probes.
"""

from unittest.mock import MagicMock

import structlog

from iam.domain.observability.workspace_probe import (
    DefaultWorkspaceProbe,
    WorkspaceProbe,
)


class TestWorkspaceProbeProtocol:
    """Tests for WorkspaceProbe protocol compliance."""

    def test_default_probe_implements_protocol(self):
        """DefaultWorkspaceProbe should implement the protocol."""
        probe = DefaultWorkspaceProbe()

        # Should have all required methods
        assert hasattr(probe, "member_added")
        assert hasattr(probe, "member_removed")
        assert hasattr(probe, "member_role_changed")

    def test_default_probe_is_runtime_compatible_with_protocol(self):
        """DefaultWorkspaceProbe should be usable wherever WorkspaceProbe is expected."""
        probe: WorkspaceProbe = DefaultWorkspaceProbe()

        # Should be callable without errors
        probe.member_added(
            workspace_id="ws-1",
            member_id="user-1",
            member_type="user",
            role="editor",
        )


class TestDefaultWorkspaceProbeInit:
    """Tests for DefaultWorkspaceProbe initialization."""

    def test_creates_with_default_logger(self):
        """Should create default logger when none provided."""
        probe = DefaultWorkspaceProbe()

        assert probe._logger is not None

    def test_creates_with_custom_logger(self):
        """Should use provided logger."""
        custom_logger = structlog.get_logger()
        probe = DefaultWorkspaceProbe(logger=custom_logger)

        assert probe._logger is custom_logger


class TestMemberAddedLogging:
    """Tests for member_added method."""

    def test_logs_member_added_at_info_level(self):
        """Should log workspace_member_added at info level."""
        mock_logger = MagicMock()
        probe = DefaultWorkspaceProbe(logger=mock_logger)

        probe.member_added(
            workspace_id="ws-123",
            member_id="user-alice",
            member_type="user",
            role="editor",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "workspace_member_added"
        assert call_args[1]["workspace_id"] == "ws-123"
        assert call_args[1]["member_id"] == "user-alice"
        assert call_args[1]["member_type"] == "user"
        assert call_args[1]["role"] == "editor"

    def test_logs_group_member_added(self):
        """Should correctly log group member type."""
        mock_logger = MagicMock()
        probe = DefaultWorkspaceProbe(logger=mock_logger)

        probe.member_added(
            workspace_id="ws-123",
            member_id="group-eng",
            member_type="group",
            role="admin",
        )

        call_args = mock_logger.info.call_args
        assert call_args[1]["member_type"] == "group"
        assert call_args[1]["role"] == "admin"


class TestMemberRemovedLogging:
    """Tests for member_removed method."""

    def test_logs_member_removed_at_info_level(self):
        """Should log workspace_member_removed at info level."""
        mock_logger = MagicMock()
        probe = DefaultWorkspaceProbe(logger=mock_logger)

        probe.member_removed(
            workspace_id="ws-123",
            member_id="user-alice",
            member_type="user",
            role="editor",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "workspace_member_removed"
        assert call_args[1]["workspace_id"] == "ws-123"
        assert call_args[1]["member_id"] == "user-alice"
        assert call_args[1]["member_type"] == "user"
        assert call_args[1]["role"] == "editor"


class TestMemberRoleChangedLogging:
    """Tests for member_role_changed method."""

    def test_logs_role_changed_at_info_level(self):
        """Should log workspace_member_role_changed at info level."""
        mock_logger = MagicMock()
        probe = DefaultWorkspaceProbe(logger=mock_logger)

        probe.member_role_changed(
            workspace_id="ws-123",
            member_id="user-alice",
            member_type="user",
            old_role="member",
            new_role="admin",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "workspace_member_role_changed"
        assert call_args[1]["workspace_id"] == "ws-123"
        assert call_args[1]["member_id"] == "user-alice"
        assert call_args[1]["member_type"] == "user"
        assert call_args[1]["old_role"] == "member"
        assert call_args[1]["new_role"] == "admin"
