"""Subprocess wrapper for OpenShell CLI commands."""

from __future__ import annotations

import logging
import subprocess
from typing import Sequence

logger = logging.getLogger("kartograph.extraction.openshell.cli")

_SECRET_PREFIXES = ("private_key=", "GCP_SA_ACCESS_TOKEN=", "KARTOGRAPH_RUNTIME_AUTH_TOKEN=")


class OpenShellCliError(RuntimeError):
    """Raised when an OpenShell CLI command fails."""


def redact_args(args: Sequence[str]) -> list[str]:
    safe: list[str] = []
    for arg in args:
        if any(arg.startswith(prefix) for prefix in _SECRET_PREFIXES):
            key = arg.split("=", 1)[0]
            safe.append(f"{key}=<redacted>")
        else:
            safe.append(arg)
    return safe


def run_openshell(
    args: Sequence[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    timeout: float | None = 120.0,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["openshell", *args]
    logger.debug("openshell_exec command=%s", " ".join(redact_args(command)))
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=text,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise OpenShellCliError(
            "openshell CLI not found on PATH; install OpenShell to use the openshell backend"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise OpenShellCliError(f"openshell command timed out: {' '.join(redact_args(command))}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "unknown error"
        raise OpenShellCliError(f"openshell {' '.join(args)} failed: {detail}")
    return result


def popen_openshell(args: Sequence[str]) -> subprocess.Popen[str]:
    command = ["openshell", *args]
    logger.debug("openshell_popen command=%s", " ".join(redact_args(command)))
    try:
        return subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise OpenShellCliError(
            "openshell CLI not found on PATH; install OpenShell to use the openshell backend"
        ) from exc
