"""Unit tests for extraction workload runtime settings."""

from __future__ import annotations

from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
)


class TestExtractionWorkloadRuntimeSettings:
    def test_parses_command_strings_into_tuple(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(
            sticky_command="sleep 3600",
            worker_command="sleep 120",
        )

        assert settings.sticky_command == ("sleep", "3600")
        assert settings.worker_command == ("sleep", "120")
