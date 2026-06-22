"""Unit tests for extraction workload runtime settings."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from extraction.infrastructure.workload_credential_issuer import (
    DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY,
)
from extraction.infrastructure.workload_runtime_factory import resolve_workload_token_signing_key
from extraction.infrastructure.workload_runtime_settings import ExtractionWorkloadRuntimeSettings


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
            workload_token_signing_key="configured-secret-at-least-32-bytes-long",
        )

        assert (
            resolve_workload_token_signing_key(settings)
            == "configured-secret-at-least-32-bytes-long"
        )

    def test_resolve_workload_token_signing_key_falls_back_in_development(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(workload_token_signing_key="")
        env = {
            "KARTOGRAPH_ENV": "development",
            "KARTOGRAPH_EXTRACTION_RUNTIME_WORKLOAD_TOKEN_SIGNING_KEY": "",
        }
        with patch.dict(os.environ, env, clear=False):
            assert (
                resolve_workload_token_signing_key(settings)
                == DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY
            )

    def test_resolve_workload_token_signing_key_rejects_missing_outside_dev(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(workload_token_signing_key="")
        env = {
            "KARTOGRAPH_ENV": "production",
            "KARTOGRAPH_EXTRACTION_RUNTIME_WORKLOAD_TOKEN_SIGNING_KEY": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="WORKLOAD_TOKEN_SIGNING_KEY must be set"):
                resolve_workload_token_signing_key(settings)

    def test_resolve_workload_token_signing_key_rejects_short_configured_value(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(workload_token_signing_key="too-short")
        with pytest.raises(ValueError, match="32"):
            resolve_workload_token_signing_key(settings)

    def test_sticky_turn_timeout_accepts_one_hour(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(sticky_turn_timeout_seconds=3600.0)

        assert settings.sticky_turn_timeout_seconds == 3600.0

    def test_empty_container_run_env_strings_do_not_crash_settings_load(self) -> None:
        env = {
            "KARTOGRAPH_EXTRACTION_RUNTIME_CONTAINER_RUN_UID": "",
            "KARTOGRAPH_EXTRACTION_RUNTIME_CONTAINER_RUN_GID": "",
            "HOST_UID": "",
            "HOST_GID": "",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = ExtractionWorkloadRuntimeSettings()

        assert settings.container_run_uid is None
        assert settings.container_run_gid is None

    def test_container_run_uid_falls_back_to_host_uid_env(self) -> None:
        with patch.dict(os.environ, {"HOST_UID": "1000", "HOST_GID": "1001"}, clear=False):
            settings = ExtractionWorkloadRuntimeSettings()

        assert settings.container_run_uid == 1000
        assert settings.container_run_gid == 1001
