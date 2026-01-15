"""Unit tests for PostgresNotifyEventSource (TDD - tests first).

These tests use mocked dependencies to test the PostgreSQL NOTIFY event
source without requiring a real database connection. The event source
listens for PostgreSQL NOTIFY events and invokes callbacks with entry UUIDs.

Following TDD, these tests are written BEFORE the implementation exists.
They should fail (red phase) until the implementation is complete.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from asyncpg_listen import Timeout


class TestPostgresNotifyEventSourceStart:
    """Tests for PostgresNotifyEventSource.start() method."""

    @pytest.mark.asyncio
    async def test_start_accepts_callback(self):
        """Test that start() accepts and stores the callback.

        The event source should accept an async callback function
        that will be invoked when NOTIFY events are received.
        """
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        callback = AsyncMock()

        # Start should not raise when given a valid callback
        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener
            # Make run complete immediately
            mock_listener.run = AsyncMock()

            await event_source.start(callback)

            # Verify the callback was stored
            assert event_source._on_event is callback

    @pytest.mark.asyncio
    async def test_start_creates_notification_listener(self):
        """Test that start() creates a NotificationListener with correct params."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        db_url = "postgresql://user:pass@host:5432/db"
        channel = "custom_channel"

        event_source = PostgresNotifyEventSource(
            db_url=db_url,
            channel=channel,
        )

        with (
            patch(
                "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
            ) as mock_listener_class,
            patch(
                "infrastructure.outbox.event_sources.postgres_notify.connect_func"
            ) as mock_connect_func,
        ):
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener
            mock_connect = MagicMock()
            mock_connect_func.return_value = mock_connect

            await event_source.start(AsyncMock())

            # Verify NotificationListener was created with connect_func
            mock_connect_func.assert_called_once_with(db_url)
            mock_listener_class.assert_called_once_with(mock_connect)


class TestPostgresNotifyEventSourceNotify:
    """Tests for NOTIFY event handling."""

    @pytest.mark.asyncio
    async def test_notify_triggers_callback_with_uuid(self):
        """Test that NOTIFY events trigger the callback with the correct UUID.

        When a PostgreSQL NOTIFY is received with a UUID payload,
        the callback should be invoked with that UUID.
        """
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        callback = AsyncMock()
        entry_id = uuid4()

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            # Capture the handler that gets registered
            handlers_passed = {}

            async def capture_run(handlers, **kwargs):
                handlers_passed.update(handlers)
                # Simulate a notification
                notification = MagicMock()
                notification.payload = str(entry_id)
                await handlers_passed["outbox_events"](notification)

            mock_listener.run = capture_run

            await event_source.start(callback)

            # Verify callback was called with the correct UUID
            callback.assert_called_once_with(entry_id)

    @pytest.mark.asyncio
    async def test_callback_receives_correct_uuid_type(self):
        """Test that callback receives UUID type, not string."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        received_values = []

        async def capture_callback(entry_id):
            received_values.append(entry_id)

        entry_id = uuid4()

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            async def capture_run(handlers, **kwargs):
                notification = MagicMock()
                notification.payload = str(entry_id)
                await handlers["outbox_events"](notification)

            mock_listener.run = capture_run

            await event_source.start(capture_callback)

            # Verify received value is UUID, not string
            assert len(received_values) == 1
            assert isinstance(received_values[0], UUID)
            assert received_values[0] == entry_id

    @pytest.mark.asyncio
    async def test_multiple_notify_events_trigger_multiple_callbacks(self):
        """Test that multiple NOTIFY events invoke callback multiple times."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        callback = AsyncMock()
        entry_ids = [uuid4() for _ in range(3)]

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            async def capture_run(handlers, **kwargs):
                # Simulate multiple notifications
                for entry_id in entry_ids:
                    notification = MagicMock()
                    notification.payload = str(entry_id)
                    await handlers["outbox_events"](notification)

            mock_listener.run = capture_run

            await event_source.start(callback)

            # Verify callback was called for each notification
            assert callback.call_count == 3
            for i, entry_id in enumerate(entry_ids):
                callback.assert_any_call(entry_id)


class TestPostgresNotifyEventSourceInvalidPayload:
    """Tests for handling invalid NOTIFY payloads."""

    @pytest.mark.asyncio
    async def test_invalid_uuid_payload_is_ignored_gracefully(self):
        """Test that NOTIFY with non-UUID payload is ignored gracefully.

        Invalid payloads should not raise exceptions or invoke the callback.
        """
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        callback = AsyncMock()

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            async def capture_run(handlers, **kwargs):
                # Simulate invalid notification payloads
                for invalid_payload in ["not-a-uuid", "", "12345", None]:
                    notification = MagicMock()
                    notification.payload = invalid_payload
                    await handlers["outbox_events"](notification)

            mock_listener.run = capture_run

            # Should not raise
            await event_source.start(callback)

            # Callback should never be called for invalid payloads
            callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_payload_is_ignored(self):
        """Test that NOTIFY with empty payload is ignored."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        callback = AsyncMock()

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            async def capture_run(handlers, **kwargs):
                notification = MagicMock()
                notification.payload = ""
                await handlers["outbox_events"](notification)

            mock_listener.run = capture_run

            await event_source.start(callback)

            callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_notification_is_ignored(self):
        """Test that Timeout notifications are ignored.

        asyncpg-listen sends Timeout objects when no notification is received
        within the timeout period. These should be silently ignored.
        """
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        callback = AsyncMock()

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            # Use real Timeout instance so isinstance() check works correctly
            timeout_instance = Timeout(channel="outbox_events")

            async def capture_run(handlers, **kwargs):
                # Simulate a timeout notification
                await handlers["outbox_events"](timeout_instance)

            mock_listener.run = capture_run

            await event_source.start(callback)

            callback.assert_not_called()


class TestPostgresNotifyEventSourceStop:
    """Tests for PostgresNotifyEventSource.stop() method."""

    @pytest.mark.asyncio
    async def test_stop_cleans_up_resources(self):
        """Test that stop() releases resources and stops the listener."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            # Simulate long-running listener that checks for stop signal
            stop_event = asyncio.Event()

            async def run_until_stopped(handlers, **kwargs):
                await stop_event.wait()

            mock_listener.run = run_until_stopped

            # Start in background
            start_task = asyncio.create_task(event_source.start(AsyncMock()))

            # Allow start to begin
            await asyncio.sleep(0.01)

            # Stop should complete gracefully
            await event_source.stop()
            stop_event.set()

            # Wait for start task to complete (with timeout)
            try:
                await asyncio.wait_for(start_task, timeout=1.0)
            except asyncio.CancelledError:
                pass  # Expected when stop cancels the task

            # Verify running flag is cleared
            assert event_source._running is False

    @pytest.mark.asyncio
    async def test_stop_sets_running_flag_false(self):
        """Test that stop() sets the internal running flag to False."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        # Manually set running to simulate started state
        event_source._running = True

        await event_source.stop()

        assert event_source._running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_safe(self):
        """Test that calling stop() before start() doesn't raise."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        # Should not raise
        await event_source.stop()

        assert event_source._running is False


class TestPostgresNotifyEventSourceGracefulShutdown:
    """Tests for graceful shutdown during NOTIFY processing."""

    @pytest.mark.asyncio
    async def test_stop_during_callback_execution(self):
        """Test that stop() properly cancels the listener task.

        When stop() is called, it should cancel the listener task cleanly.
        The event source should handle cancellation without corrupting state.
        """
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        callback_started = asyncio.Event()
        callback_cancelled = False

        async def slow_callback(entry_id):
            nonlocal callback_cancelled
            callback_started.set()
            try:
                # Wait indefinitely - will be cancelled by stop()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                callback_cancelled = True
                raise

        entry_id = uuid4()

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            async def capture_run(handlers, **kwargs):
                notification = MagicMock()
                notification.payload = str(entry_id)
                await handlers["outbox_events"](notification)

            mock_listener.run = capture_run

            # Start the event source in background
            start_task = asyncio.create_task(event_source.start(slow_callback))

            # Wait for callback to start
            await asyncio.wait_for(callback_started.wait(), timeout=1.0)

            # Initiate stop while callback is running - should cancel the task
            stop_task = asyncio.create_task(event_source.stop())

            # Both tasks should complete
            await asyncio.wait_for(
                asyncio.gather(start_task, stop_task, return_exceptions=True),
                timeout=1.0,
            )

            # Verify stop() properly cancelled the listener task
            assert event_source._running is False
            assert callback_cancelled

    @pytest.mark.asyncio
    async def test_no_callback_invoked_after_stop(self):
        """Test that no callbacks are invoked after stop() is called."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        callback = AsyncMock()
        entry_id = uuid4()

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            stop_called = asyncio.Event()

            async def capture_run(handlers, **kwargs):
                # Wait for stop to be called
                await stop_called.wait()
                # Try to invoke handler after stop
                notification = MagicMock()
                notification.payload = str(entry_id)
                await handlers["outbox_events"](notification)

            mock_listener.run = capture_run

            # Start in background
            start_task = asyncio.create_task(event_source.start(callback))

            await asyncio.sleep(0.01)

            # Stop and signal that stop was called
            await event_source.stop()
            stop_called.set()

            # Wait for start to finish
            try:
                await asyncio.wait_for(start_task, timeout=1.0)
            except asyncio.CancelledError:
                pass

            # Callback should not be called after stop
            callback.assert_not_called()


class TestPostgresNotifyEventSourceConformsToProtocol:
    """Tests verifying PostgresNotifyEventSource implements OutboxEventSource protocol."""

    def test_implements_outbox_event_source_protocol(self):
        """Test that PostgresNotifyEventSource implements OutboxEventSource protocol."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.ports import OutboxEventSource

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
        )

        # Verify it has the required methods
        assert hasattr(event_source, "start")
        assert hasattr(event_source, "stop")
        assert callable(event_source.start)
        assert callable(event_source.stop)

        # Verify it's recognized as implementing the protocol
        assert isinstance(event_source, OutboxEventSource)

    def test_default_channel_name(self):
        """Test that default channel name is 'outbox_events'."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
        )

        assert event_source._channel == "outbox_events"

    def test_custom_channel_name(self):
        """Test that custom channel name can be specified."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="my_custom_channel",
        )

        assert event_source._channel == "my_custom_channel"


class TestPostgresNotifyEventSourceProbeIntegration:
    """Tests for observability probe integration."""

    @pytest.mark.asyncio
    async def test_start_calls_probe_event_source_started(self):
        """Test that start() calls probe.event_source_started()."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.observability import EventSourceProbe

        mock_probe = MagicMock(spec=EventSourceProbe)

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            channel="outbox_events",
            probe=mock_probe,
        )

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener
            mock_listener.run = AsyncMock()

            await event_source.start(AsyncMock())

            mock_probe.event_source_started.assert_called_once_with("outbox_events")

    @pytest.mark.asyncio
    async def test_stop_calls_probe_event_source_stopped(self):
        """Test that stop() calls probe.event_source_stopped()."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.observability import EventSourceProbe

        mock_probe = MagicMock(spec=EventSourceProbe)

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            probe=mock_probe,
        )

        await event_source.stop()

        mock_probe.event_source_stopped.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_notification_calls_probe_notification_received(self):
        """Test that valid notification calls probe.notification_received()."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.observability import EventSourceProbe

        mock_probe = MagicMock(spec=EventSourceProbe)
        entry_id = uuid4()

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            probe=mock_probe,
        )

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            async def capture_run(handlers, **kwargs):
                notification = MagicMock()
                notification.payload = str(entry_id)
                await handlers["outbox_events"](notification)

            mock_listener.run = capture_run

            await event_source.start(AsyncMock())

            mock_probe.notification_received.assert_called_once_with(entry_id)

    @pytest.mark.asyncio
    async def test_invalid_notification_calls_probe_invalid_notification_ignored(self):
        """Test that invalid notification calls probe.invalid_notification_ignored()."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.observability import EventSourceProbe

        mock_probe = MagicMock(spec=EventSourceProbe)

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            probe=mock_probe,
        )

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            async def capture_run(handlers, **kwargs):
                notification = MagicMock()
                notification.payload = "not-a-valid-uuid"
                await handlers["outbox_events"](notification)

            mock_listener.run = capture_run

            await event_source.start(AsyncMock())

            mock_probe.invalid_notification_ignored.assert_called_once_with(
                "not-a-valid-uuid", "Invalid UUID format"
            )

    @pytest.mark.asyncio
    async def test_listener_exception_calls_probe_listener_error(self):
        """Test that listener exception calls probe.listener_error()."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.observability import EventSourceProbe

        mock_probe = MagicMock(spec=EventSourceProbe)

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            probe=mock_probe,
        )

        with patch(
            "infrastructure.outbox.event_sources.postgres_notify.NotificationListener"
        ) as mock_listener_class:
            mock_listener = AsyncMock()
            mock_listener_class.return_value = mock_listener

            async def raise_error(*args, **kwargs):
                raise ConnectionError("Connection refused")

            mock_listener.run = raise_error

            await event_source.start(AsyncMock())

            mock_probe.listener_error.assert_called_once_with("Connection refused")

    def test_default_probe_is_used_when_none_provided(self):
        """Test that DefaultEventSourceProbe is used when no probe is provided."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.observability import DefaultEventSourceProbe

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
        )

        assert isinstance(event_source._probe, DefaultEventSourceProbe)

    def test_custom_probe_is_used_when_provided(self):
        """Test that custom probe is used when provided."""
        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.observability import EventSourceProbe

        mock_probe = MagicMock(spec=EventSourceProbe)

        event_source = PostgresNotifyEventSource(
            db_url="postgresql://test:test@localhost/test",
            probe=mock_probe,
        )

        assert event_source._probe is mock_probe
