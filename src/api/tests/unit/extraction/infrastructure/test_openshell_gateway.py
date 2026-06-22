"""Unit tests for OpenShell gateway helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from extraction.infrastructure.openshell.cli import (
    OpenShellCliError,
    openshell_subprocess_env,
)
from extraction.infrastructure.openshell.gateway import (
    ensure_gateway_registered,
    gateway_is_connected,
    gateway_is_registered,
)


class TestOpenShellSubprocessEnv:
    def test_maps_kartograph_openshell_settings_to_cli_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("OPENSHELL_GATEWAY", raising=False)
        monkeypatch.delenv("OPENSHELL_GATEWAY_ENDPOINT", raising=False)
        monkeypatch.setenv(
            "KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_XDG_CONFIG_HOME", "/root/.config"
        )
        monkeypatch.setenv(
            "KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_GATEWAY_NAME", "openshell"
        )
        monkeypatch.setenv(
            "KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_GATEWAY_URL",
            "https://host.docker.internal:17670",
        )

        env = openshell_subprocess_env()

        assert env["XDG_CONFIG_HOME"] == "/root/.config"
        assert env["OPENSHELL_GATEWAY"] == "openshell"
        assert env["OPENSHELL_GATEWAY_ENDPOINT"] == "https://host.docker.internal:17670"


class TestGatewayIsRegistered:
    def test_returns_true_when_gateway_get_succeeds(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.gateway.run_openshell",
            return_value=MagicMock(returncode=0),
        ) as run:
            assert gateway_is_registered(gateway_name="openshell") is True
        run.assert_called_once_with(
            ["gateway", "--gateway", "openshell", "info"],
            check=False,
        )

    def test_returns_false_when_gateway_get_fails(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.gateway.run_openshell",
            return_value=MagicMock(returncode=1),
        ):
            assert gateway_is_registered(gateway_name="openshell") is False


class TestGatewayIsConnected:
    def test_returns_true_when_status_shows_connected(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.gateway.run_openshell",
            return_value=MagicMock(returncode=0, stdout="Connected", stderr=""),
        ):
            assert gateway_is_connected() is True

    def test_returns_false_when_no_gateway_configured(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.gateway.run_openshell",
            return_value=MagicMock(
                returncode=1,
                stdout="",
                stderr="No gateway configured",
            ),
        ):
            assert gateway_is_connected() is False


class TestEnsureGatewayRegistered:
    def test_skips_gateway_add_when_registered_and_connected(self) -> None:
        with (
            patch(
                "extraction.infrastructure.openshell.gateway.gateway_is_registered",
                return_value=True,
            ),
            patch(
                "extraction.infrastructure.openshell.gateway.gateway_is_connected",
                return_value=True,
            ),
            patch("extraction.infrastructure.openshell.gateway.run_openshell") as run,
        ):
            ensure_gateway_registered(
                gateway_name="openshell",
                gateway_url="https://host.docker.internal:17670",
            )
        run.assert_not_called()

    def test_raises_when_registered_but_unreachable(self) -> None:
        with (
            patch(
                "extraction.infrastructure.openshell.gateway.gateway_is_registered",
                return_value=True,
            ),
            patch(
                "extraction.infrastructure.openshell.gateway.gateway_is_connected",
                return_value=False,
            ),
        ):
            with pytest.raises(OpenShellCliError, match="not reachable"):
                ensure_gateway_registered(
                    gateway_name="openshell",
                    gateway_url="https://host.docker.internal:17670",
                )

    def test_skips_gateway_add_when_connected_without_registration(self) -> None:
        with (
            patch(
                "extraction.infrastructure.openshell.gateway.gateway_is_registered",
                return_value=False,
            ),
            patch(
                "extraction.infrastructure.openshell.gateway.gateway_is_connected",
                return_value=True,
            ),
            patch("extraction.infrastructure.openshell.gateway.run_openshell") as run,
        ):
            ensure_gateway_registered(
                gateway_name="openshell",
                gateway_url="https://127.0.0.1:17670",
            )
        run.assert_not_called()

    def test_registers_gateway_when_not_configured(self) -> None:
        with (
            patch(
                "extraction.infrastructure.openshell.gateway.gateway_is_registered",
                return_value=False,
            ),
            patch(
                "extraction.infrastructure.openshell.gateway.gateway_is_connected",
                return_value=False,
            ),
            patch("extraction.infrastructure.openshell.gateway.run_openshell") as run,
        ):
            ensure_gateway_registered(
                gateway_name="openshell",
                gateway_url="https://127.0.0.1:17670",
            )
        run.assert_called_once_with(
            [
                "gateway",
                "add",
                "https://127.0.0.1:17670",
                "--local",
                "--name",
                "openshell",
            ],
            timeout=30.0,
        )
