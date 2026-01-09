"""Unit tests for outbox worker observability probes.

These tests verify the probe protocol and default implementation.
"""

from uuid import uuid4

from shared_kernel.outbox.observability import (
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
