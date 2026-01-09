"""Unit tests for CompositeTranslator with observability.

These tests verify that the CompositeTranslator correctly logs translator
registrations using the observability probe.
"""

from unittest.mock import Mock


from infrastructure.outbox.composite import CompositeTranslator
from shared_kernel.outbox.observability import OutboxWorkerProbe


class MockTranslator:
    """Mock translator for testing."""

    def __init__(self, event_types: frozenset[str]):
        self._event_types = event_types

    def supported_event_types(self) -> frozenset[str]:
        return self._event_types

    def translate(self, event_type: str, payload: dict) -> list:
        return []


class TestCompositeTranslatorObservability:
    """Tests for CompositeTranslator probe integration."""

    def test_register_calls_probe_with_context_name(self):
        """register should call probe.translator_registered with context name."""
        probe = Mock(spec=OutboxWorkerProbe)
        translator = CompositeTranslator(probe=probe)
        mock_translator = MockTranslator(frozenset({"GroupCreated", "GroupDeleted"}))

        translator.register(mock_translator, context_name="iam")

        probe.translator_registered.assert_called_once_with(
            "iam", frozenset({"GroupCreated", "GroupDeleted"})
        )

    def test_register_without_context_name_uses_class_name(self):
        """register without context_name should use translator class name."""
        probe = Mock(spec=OutboxWorkerProbe)
        translator = CompositeTranslator(probe=probe)
        mock_translator = MockTranslator(frozenset({"SimpleEvent"}))

        translator.register(mock_translator)

        probe.translator_registered.assert_called_once_with(
            "MockTranslator", frozenset({"SimpleEvent"})
        )

    def test_register_without_probe_does_not_raise(self):
        """register without probe should work normally."""
        translator = CompositeTranslator()  # No probe
        mock_translator = MockTranslator(frozenset({"Event1"}))

        # Should not raise
        translator.register(mock_translator)

        assert "Event1" in translator.supported_event_types()

    def test_multiple_registrations_call_probe_each_time(self):
        """Each registration should call the probe."""
        probe = Mock(spec=OutboxWorkerProbe)
        translator = CompositeTranslator(probe=probe)

        translator.register(MockTranslator(frozenset({"Event1"})), context_name="ctx1")
        translator.register(MockTranslator(frozenset({"Event2"})), context_name="ctx2")

        assert probe.translator_registered.call_count == 2
