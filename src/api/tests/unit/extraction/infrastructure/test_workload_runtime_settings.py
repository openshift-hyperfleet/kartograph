"""Unit tests for extraction workload runtime settings."""

from __future__ import annotations

from extraction.infrastructure.workload_runtime_factory import resolve_workload_token_signing_key
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
)


class TestExtractionWorkloadRuntimeSettings:
    def test_default_sticky_command_uses_image_entrypoint(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings()

        assert settings.sticky_command == ()

    def test_parses_command_strings_into_tuple(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(
            sticky_command="sleep 3600",
            worker_command="sleep 120",
        )

        assert settings.sticky_command == ("sleep", "3600")
        assert settings.worker_command == ("sleep", "120")

    def test_resolve_workload_token_signing_key_uses_configured_value(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(
            workload_token_signing_key="configured-secret",
        )

        assert resolve_workload_token_signing_key(settings) == "configured-secret"

    def test_resolve_workload_token_signing_key_falls_back_to_dev_default(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(workload_token_signing_key="")

        assert resolve_workload_token_signing_key(settings)
