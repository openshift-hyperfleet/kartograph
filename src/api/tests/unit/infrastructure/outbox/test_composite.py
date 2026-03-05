"""Unit tests for CompositeEventHandler.

These tests verify that the CompositeEventHandler correctly registers
handlers, dispatches events with fan-out, and integrates with the
observability probe.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from infrastructure.outbox.composite import CompositeEventHandler
from shared_kernel.outbox.observability import OutboxWorkerProbe
from shared_kernel.outbox.ports import EventHandler


class MockHandler:
    """Mock handler for testing supported_event_types routing."""

    def __init__(self, event_types: frozenset[str]) -> None:
        self._event_types = event_types
        self.handle = AsyncMock()

    def supported_event_types(self) -> frozenset[str]:
        return self._event_types


class TestCompositeEventHandler:
    """Tests for CompositeEventHandler."""

    def test_implements_event_handler_protocol(self):
        """CompositeEventHandler should satisfy the EventHandler protocol."""
        handler = CompositeEventHandler()
        assert isinstance(handler, EventHandler)

    def test_register_calls_probe_with_handler_name(self):
        """register should call probe.handler_registered with name and event_types."""
        probe = MagicMock(spec=OutboxWorkerProbe)
        composite = CompositeEventHandler(probe=probe)
        mock_handler = MockHandler(frozenset({"GroupCreated", "GroupDeleted"}))

        composite.register(mock_handler, handler_name="iam")

        probe.handler_registered.assert_called_once_with(
            "iam", frozenset({"GroupCreated", "GroupDeleted"})
        )

    def test_register_without_name_uses_class_name(self):
        """register without handler_name should use handler.__class__.__name__."""
        probe = MagicMock(spec=OutboxWorkerProbe)
        composite = CompositeEventHandler(probe=probe)
        mock_handler = MockHandler(frozenset({"SimpleEvent"}))

        composite.register(mock_handler)

        probe.handler_registered.assert_called_once_with(
            "MockHandler", frozenset({"SimpleEvent"})
        )

    def test_register_without_probe_does_not_raise(self):
        """register without probe should work normally."""
        composite = CompositeEventHandler()  # No probe
        mock_handler = MockHandler(frozenset({"Event1"}))

        # Should not raise
        composite.register(mock_handler)

        assert "Event1" in composite.supported_event_types()

    def test_supported_event_types_union(self):
        """supported_event_types should return union of all registered handlers."""
        composite = CompositeEventHandler()
        handler_a = MockHandler(frozenset({"EventA", "EventB"}))
        handler_b = MockHandler(frozenset({"EventB", "EventC"}))

        composite.register(handler_a)
        composite.register(handler_b)

        assert composite.supported_event_types() == frozenset(
            {"EventA", "EventB", "EventC"}
        )

    @pytest.mark.asyncio
    async def test_handle_dispatches_to_correct_handler(self):
        """handle should dispatch only to handlers registered for that event type."""
        composite = CompositeEventHandler()
        handler_a = MockHandler(frozenset({"EventA"}))
        handler_b = MockHandler(frozenset({"EventB"}))

        composite.register(handler_a)
        composite.register(handler_b)

        payload = {"key": "value"}
        await composite.handle("EventA", payload)

        handler_a.handle.assert_called_once_with("EventA", payload)
        handler_b.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_fans_out_to_multiple_handlers(self):
        """handle should call all handlers registered for the same event type."""
        composite = CompositeEventHandler()
        handler_a = MockHandler(frozenset({"SharedEvent"}))
        handler_b = MockHandler(frozenset({"SharedEvent"}))

        composite.register(handler_a)
        composite.register(handler_b)

        payload = {"data": "test"}
        await composite.handle("SharedEvent", payload)

        handler_a.handle.assert_called_once_with("SharedEvent", payload)
        handler_b.handle.assert_called_once_with("SharedEvent", payload)

    @pytest.mark.asyncio
    async def test_handle_raises_for_unknown_event_type(self):
        """handle should raise ValueError for unregistered event types."""
        composite = CompositeEventHandler()
        handler = MockHandler(frozenset({"KnownEvent"}))
        composite.register(handler)

        with pytest.raises(ValueError, match="No handler registered for event type"):
            await composite.handle("UnknownEvent", {})

    @pytest.mark.asyncio
    async def test_handle_does_not_call_probe_event_dispatching(self):
        """handle should NOT call probe.event_dispatching (worker owns that)."""
        probe = MagicMock(spec=OutboxWorkerProbe)
        composite = CompositeEventHandler(probe=probe)
        handler_a = MockHandler(frozenset({"EventX"}))

        composite.register(handler_a)

        await composite.handle("EventX", {"some": "data"})

        probe.event_dispatching.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_is_idempotent(self):
        """Registering the same handler twice should not duplicate dispatch."""
        handler = MagicMock()
        handler.supported_event_types.return_value = frozenset({"EventA"})
        handler.handle = AsyncMock()

        composite = CompositeEventHandler()
        composite.register(handler)
        composite.register(handler)  # duplicate

        await composite.handle("EventA", {"key": "value"})

        # Should only be called once, not twice
        handler.handle.assert_awaited_once_with("EventA", {"key": "value"})
