"""Domain observability probes for OpenShell sandbox lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class OpenShellPolicyAppliedObservation:
    sandbox_name: str
    policy_name: str
    enforcement: str
    endpoint_count: int
    ui_mode: str | None = None
    job_id: str | None = None


@dataclass(frozen=True)
class OpenShellSandboxLifecycleObservation:
    sandbox_name: str
    action: str
    image: str | None = None
    forward_port: int | None = None
    session_id: str | None = None
    job_id: str | None = None


class OpenShellRuntimeProbe(Protocol):
    def policy_applied(self, observation: OpenShellPolicyAppliedObservation) -> None:
        """Emit when network/L7 policy is applied to a sandbox."""

    def sandbox_lifecycle(self, observation: OpenShellSandboxLifecycleObservation) -> None:
        """Emit when a sandbox is created, started, or deleted."""


class LoggingOpenShellRuntimeProbe:
    """Default probe aligned with OCSF network-activity semantics."""

    def __init__(self, *, sink: Any | None = None) -> None:
        import logging

        self._logger = sink or logging.getLogger("kartograph.extraction.openshell")

    def policy_applied(self, observation: OpenShellPolicyAppliedObservation) -> None:
        self._logger.info(
            "openshell_policy_applied sandbox=%s policy=%s enforcement=%s endpoints=%s ui_mode=%s job_id=%s",
            observation.sandbox_name,
            observation.policy_name,
            observation.enforcement,
            observation.endpoint_count,
            observation.ui_mode,
            observation.job_id,
        )

    def sandbox_lifecycle(self, observation: OpenShellSandboxLifecycleObservation) -> None:
        self._logger.info(
            "openshell_sandbox_lifecycle sandbox=%s action=%s image=%s forward_port=%s session_id=%s job_id=%s",
            observation.sandbox_name,
            observation.action,
            observation.image,
            observation.forward_port,
            observation.session_id,
            observation.job_id,
        )
