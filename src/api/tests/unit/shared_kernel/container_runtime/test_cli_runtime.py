"""Unit tests for CLI-backed container runtime."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared_kernel.container_runtime.cli_runtime import CliContainerRuntime
from shared_kernel.container_runtime.ports import ContainerRunSpec, ContainerRuntimeError


class TestCliContainerRuntime:
    def test_run_launches_detached_container_with_labels_env_and_binds(self) -> None:
        runtime = CliContainerRuntime(binary="docker")

        with patch("shared_kernel.container_runtime.cli_runtime.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="abc123\n", stderr="")

            result = runtime.run(
                ContainerRunSpec(
                    image="busybox:1.36",
                    name="kartograph-sticky-session-1",
                    env={"KARTOGRAPH_WORKLOAD_TOKEN": "secret"},
                    labels={
                        "kartograph.runtime.kind": "sticky",
                        "kartograph.session_id": "session-1",
                    },
                    binds=("/host/skills:/app/skills:ro",),
                    network="kartograph_kartograph",
                    command=("sleep", "3600"),
                )
            )

        assert result.container_id == "abc123"
        command = run.call_args.args[0]
        assert "--volume" in command
        assert "/host/skills:/app/skills:ro" in command
        assert "--network" in command
        assert "kartograph_kartograph" in command

    def test_run_launches_detached_container_with_labels_and_env(self) -> None:
        runtime = CliContainerRuntime(binary="docker")

        with patch("shared_kernel.container_runtime.cli_runtime.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="abc123\n", stderr="")

            result = runtime.run(
                ContainerRunSpec(
                    image="busybox:1.36",
                    name="kartograph-sticky-session-1",
                    env={"KARTOGRAPH_WORKLOAD_TOKEN": "secret"},
                    labels={
                        "kartograph.runtime.kind": "sticky",
                        "kartograph.session_id": "session-1",
                    },
                    command=("sleep", "3600"),
                )
            )

        assert result.container_id == "abc123"
        assert result.name == "kartograph-sticky-session-1"
        command = run.call_args.args[0]
        assert command[0] == "docker"
        assert "run" in command
        assert "--detach" in command
        assert "busybox:1.36" in command

    def test_run_raises_when_cli_fails(self) -> None:
        runtime = CliContainerRuntime(binary="docker")

        with patch("shared_kernel.container_runtime.cli_runtime.subprocess.run") as run:
            run.return_value = MagicMock(
                returncode=125,
                stdout="",
                stderr="image not found",
            )

            with pytest.raises(ContainerRuntimeError, match="image not found"):
                runtime.run(ContainerRunSpec(image="missing:latest"))

    def test_stop_remove_and_is_running_delegate_to_cli(self) -> None:
        runtime = CliContainerRuntime(binary="podman")

        with patch("shared_kernel.container_runtime.cli_runtime.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),
                MagicMock(returncode=0, stdout="", stderr=""),
                MagicMock(returncode=0, stdout="true\n", stderr=""),
            ]

            runtime.stop("abc123", timeout_seconds=5)
            runtime.remove("abc123", force=True)
            assert runtime.is_running("abc123") is True

        assert run.call_args_list[0].args[0][:3] == ["podman", "stop", "-t"]

    def test_is_running_returns_false_for_missing_container(self) -> None:
        runtime = CliContainerRuntime(binary="docker")

        with patch("shared_kernel.container_runtime.cli_runtime.subprocess.run") as run:
            run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: No such object: abc123",
            )

            assert runtime.is_running("abc123") is False
