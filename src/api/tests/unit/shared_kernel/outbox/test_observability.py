"""Unit tests for outbox worker observability probes.

These tests verify the probe protocol and default implementation.
"""

from uuid import uuid4

from shared_kernel.outbox.observability import (
    DefaultEventSourceProbe,
    DefaultOutboxWorkerProbe,
)


class TestOutboxWorkerProbeProtocol:
    """Tests for OutboxWorkerProbe protocol methods."""

    def test_default_probe_has_poll_loop_error(self):
        """DefaultOutboxWorkerProbe should have poll_loop_error method."""
        probe = DefaultOutboxWorkerProbe()
        assert hasattr(probe, "poll_loop_error")
        assert callable(probe.poll_loop_error)

    def test_poll_loop_error_accepts_error_string(self):
        """poll_loop_error should accept an error message."""
        probe = DefaultOutboxWorkerProbe()
        # Should not raise
        probe.poll_loop_error("Connection timeout")

    def test_default_probe_has_event_translated(self):
        """DefaultOutboxWorkerProbe should have event_translated method."""
        probe = DefaultOutboxWorkerProbe()
        assert hasattr(probe, "event_translated")
        assert callable(probe.event_translated)

    def test_event_translated_accepts_parameters(self):
        """event_translated should accept entry_id, event_type, and operation_count."""
        probe = DefaultOutboxWorkerProbe()
        # Should not raise
        probe.event_translated(uuid4(), "GroupCreated", 2)

    def test_event_translated_logs_operation_count(self):
        """event_translated provides visibility into how many SpiceDB ops each event produces."""
        probe = DefaultOutboxWorkerProbe()
        # Zero operations is valid (but worth observing - could indicate misconfiguration)
        probe.event_translated(uuid4(), "UnknownEvent", 0)
        # Multiple operations is common
        probe.event_translated(uuid4(), "MemberAdded", 1)

    def test_default_probe_has_translator_registered(self):
        """DefaultOutboxWorkerProbe should have translator_registered method."""
        probe = DefaultOutboxWorkerProbe()
        assert hasattr(probe, "translator_registered")
        assert callable(probe.translator_registered)

    def test_translator_registered_accepts_parameters(self):
        """translator_registered should accept context_name and event_types."""
        probe = DefaultOutboxWorkerProbe()
        # Should not raise
        probe.translator_registered(
            "iam", frozenset({"GroupCreated", "MemberAdded", "MemberRemoved"})
        )

    def test_translator_registered_logs_event_types(self):
        """translator_registered provides visibility into registered plugins."""
        probe = DefaultOutboxWorkerProbe()
        # Single event type
        probe.translator_registered("simple", frozenset({"SimpleEvent"}))
        # Multiple event types
        probe.translator_registered(
            "iam",
            frozenset({"GroupCreated", "GroupDeleted", "MemberAdded", "MemberRemoved"}),
        )

    def test_default_probe_implements_all_protocol_methods(self):
        """DefaultOutboxWorkerProbe should implement all protocol methods."""
        probe = DefaultOutboxWorkerProbe()

        # All these methods should exist and be callable
        probe.worker_started()
        probe.worker_stopped()
        probe.event_processed(uuid4(), "GroupCreated")
        probe.event_processing_failed(uuid4(), "Error message", 1)
        probe.event_moved_to_dlq(uuid4(), "GroupCreated", "Max retries exceeded")
        probe.batch_processed(5)
        probe.listen_loop_started()
        probe.poll_loop_started()
        probe.poll_loop_error("Connection error")
        probe.event_translated(uuid4(), "GroupCreated", 2)
        probe.translator_registered("iam", frozenset({"GroupCreated"}))


class TestEventSourceProbeProtocol:
    """Tests for EventSourceProbe protocol methods."""

    def test_default_probe_has_event_source_started(self):
        """DefaultEventSourceProbe should have event_source_started method."""
        probe = DefaultEventSourceProbe()
        assert hasattr(probe, "event_source_started")
        assert callable(probe.event_source_started)

    def test_event_source_started_accepts_channel(self):
        """event_source_started should accept a channel name."""
        probe = DefaultEventSourceProbe()
        # Should not raise
        probe.event_source_started("outbox_events")

    def test_default_probe_has_event_source_stopped(self):
        """DefaultEventSourceProbe should have event_source_stopped method."""
        probe = DefaultEventSourceProbe()
        assert hasattr(probe, "event_source_stopped")
        assert callable(probe.event_source_stopped)

    def test_event_source_stopped_no_args(self):
        """event_source_stopped should require no arguments."""
        probe = DefaultEventSourceProbe()
        # Should not raise
        probe.event_source_stopped()

    def test_default_probe_has_notification_received(self):
        """DefaultEventSourceProbe should have notification_received method."""
        probe = DefaultEventSourceProbe()
        assert hasattr(probe, "notification_received")
        assert callable(probe.notification_received)

    def test_notification_received_accepts_entry_id(self):
        """notification_received should accept an entry UUID."""
        probe = DefaultEventSourceProbe()
        # Should not raise
        probe.notification_received(uuid4())

    def test_default_probe_has_invalid_notification_ignored(self):
        """DefaultEventSourceProbe should have invalid_notification_ignored method."""
        probe = DefaultEventSourceProbe()
        assert hasattr(probe, "invalid_notification_ignored")
        assert callable(probe.invalid_notification_ignored)

    def test_invalid_notification_ignored_accepts_parameters(self):
        """invalid_notification_ignored should accept payload and reason."""
        probe = DefaultEventSourceProbe()
        # Should not raise
        probe.invalid_notification_ignored("not-a-uuid", "Invalid UUID format")

    def test_default_probe_has_listener_error(self):
        """DefaultEventSourceProbe should have listener_error method."""
        probe = DefaultEventSourceProbe()
        assert hasattr(probe, "listener_error")
        assert callable(probe.listener_error)

    def test_listener_error_accepts_error_string(self):
        """listener_error should accept an error message."""
        probe = DefaultEventSourceProbe()
        # Should not raise
        probe.listener_error("Connection refused")

    def test_default_probe_implements_all_protocol_methods(self):
        """DefaultEventSourceProbe should implement all protocol methods."""
        probe = DefaultEventSourceProbe()

        # All these methods should exist and be callable
        probe.event_source_started("outbox_events")
        probe.event_source_stopped()
        probe.notification_received(uuid4())
        probe.invalid_notification_ignored("bad-payload", "Invalid format")
        probe.listener_error("Connection error")
